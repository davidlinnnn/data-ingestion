"""Run in two different Pods with the same operation and participant names a/b."""
import json
import os
from pathlib import Path
import sys
import time
import boto3
from object_store import Store
client=boto3.client('s3',endpoint_url='http://objects:9000')
store=Store(client,'pdf-prototype',os.environ.get('PDF_STORE_PREFIX','linux-v1'))
operation,participant=sys.argv[1:3]
def barrier(key):
    store.put_once(store.prefix+'race-ready/'+operation+'/'+participant,b'ready')
    until=time.monotonic()+60
    while time.monotonic()<until:
        if all(store.get(store.prefix+'race-ready/'+operation+'/'+p) for p in ('a','b')):
            return
        time.sleep(.1)
    raise RuntimeError('second contender did not reach barrier')
result=store.publish(operation,{'result':json.dumps({'pod':os.environ['HOSTNAME'],'participant':participant}).encode()},after_upload=barrier)
print(json.dumps({'pod':os.environ['HOSTNAME'],'participant':participant,'accepted':result}),flush=True)
