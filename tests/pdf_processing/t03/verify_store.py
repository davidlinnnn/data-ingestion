"""Real selected-provider contracts, including targeted transport fault injection."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from pdf_processing.object_store import Store, StoreFailure


def fails(action, category, code):
    try:
        action()
    except StoreFailure as error:
        assert (error.category,error.code)==(category,code), (error.category,error.code)
    else:
        raise AssertionError('Expected explicit failure: '+code)


def verify(client, bucket):
    prefix = 'contract-'+uuid.uuid4().hex
    store = Store(client, bucket, prefix)
    assert store.resolve('missing') is None
    original = store.publish('damaged', {'evidence.txt': b'original'})
    client.put_object(Bucket=bucket, Key=original['files'][0]['key'], Body=b'tampered')
    fails(lambda:store.resolve('damaged'),'integrity','committed_payload_corrupt')
    assert client.get_object(Bucket=bucket, Key=store.registry_key('damaged'))['Body'].read() == json.dumps(original, sort_keys=True).encode()
    missing = store.publish('missing-payload', {'evidence.txt': b'original'})
    client.delete_object(Bucket=bucket,Key=missing['files'][0]['key'])
    fails(lambda:store.resolve('missing-payload'),'integrity','committed_payload_missing')
    client.put_object(Bucket=bucket,Key=store.registry_key('invalid-manifest'),Body=b'{broken')
    fails(lambda:store.resolve('invalid-manifest'),'integrity','committed_manifest_invalid')
    client.put_object(Bucket=bucket,Key=store.registry_key('duplicate'),Body=json.dumps({
        **original,'operation':'duplicate','files':original['files']*2}).encode())
    fails(lambda:store.resolve('duplicate'),'integrity','committed_manifest_invalid')

    raced = Store(client,bucket,prefix+'-race')
    barrier = Barrier(2)
    def race(n):
        return raced.publish('race',{'payload':str(n).encode()},after_upload=lambda _:barrier.wait(10))
    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted = list(pool.map(race,range(2)))
    assert accepted[0] == accepted[1] == raced.resolve('race')
    inventory = raced.inventory(capacity_bytes=1)
    assert inventory['registration_count']==1 and inventory['registered_artifact_count']==1
    assert inventory['orphan_classification_complete'] and len(inventory['orphan_objects'])==1
    assert inventory['capacity_exceeded'] and inventory['retention_action']=='none'
    listed=client.list_objects_v2(Bucket=bucket,Prefix=raced.prefix+'diagnostics/')['Contents']
    assert len(listed)==1
    raw=raced.get(listed[0]['Key']); assert raw is not None
    diagnostic=json.loads(raw)
    assert diagnostic['winner']==accepted[0] and diagnostic['loser']!=accepted[0]
    partial=raced.inventory(max_objects=1)
    assert not partial['complete'] and partial['orphan_objects'] is None

    # A real service accepts the write; only the returning transport ACK is lost.
    class LoseWriteAcknowledgement:
        def __init__(self): self.lost=False
        def __getattr__(self,name): return getattr(client,name)
        def put_object(self,**args):
            value=client.put_object(**args)
            if '/registered/' in args['Key'] and not self.lost:
                self.lost=True
                raise TimeoutError('Injected lost response after real accepted write')
            return value
    lossy=Store(LoseWriteAcknowledgement(),bucket,prefix+'-lost')
    committed=lossy.publish('ack',{'payload':b'accepted'})
    assert committed == lossy.resolve('ack')
    before=lossy.io['put_bytes']
    assert lossy.publish('ack',{'payload':b'must not overwrite'})==committed
    assert lossy.io['put_bytes']==before

    import boto3
    from botocore.config import Config
    bad=boto3.client('s3',endpoint_url=client.meta.endpoint_url,
        aws_access_key_id='invalid',aws_secret_access_key='invalid')
    fails(lambda:Store(bad,bucket,prefix).resolve('x'),'configuration','storage_access_denied')
    fails(lambda:Store(client,'t03-nonexistent-bucket',prefix).resolve('x'),'configuration','storage_configuration')
    offline=boto3.client('s3',endpoint_url='http://127.0.0.1:9',
        config=Config(connect_timeout=.1,read_timeout=.1,retries={'max_attempts':0}))
    fails(lambda:Store(offline,bucket,prefix).resolve('x'),'storage','storage_unavailable')
    return {'prefix':prefix,'checks':['missing_registration','committed_corrupt','committed_missing',
        'invalid_manifest','duplicate_manifest','concurrent_winner','divergence','orphan_inventory',
        'bounded_inventory','capacity','lost_write_ack','intact_reuse','authorization','configuration','transient'],
        'race_inventory':inventory}


if __name__ == '__main__':
    import boto3, os
    result = verify(boto3.client('s3', endpoint_url=os.environ['OBJECT_ENDPOINT']), os.environ['OBJECT_BUCKET'])
    print(json.dumps(result, indent=2,default=str))
