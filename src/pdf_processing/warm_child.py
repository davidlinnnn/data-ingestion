"""Private newline protocol for one native converter; any failure exits the child."""
import json
import sys
from .execution import ChildFailure
from .parse import ParseRequest, execute


def main():
    correlation = None
    def receive():
        nonlocal correlation
        line = sys.stdin.readline()
        if not line:
            return None
        envelope = json.loads(line)
        if envelope.get('version') != 1 or not isinstance(envelope.get('request_id'), str):
            raise ChildFailure('integrity', 'invalid_child_request')
        correlation = envelope['request_id']
        return ParseRequest.from_json(envelope['request'])
    def notify(kind, **data):
        print(json.dumps({'protocol':'pdf-warm-v1', 'request_id':correlation,
                          'kind':kind, **data}), flush=True)
    try:
        request = receive()
        if request is not None:
            execute(request, receive, notify)
    except Exception as error:
        category, code = (error.category, error.code) if isinstance(error, ChildFailure) else ('parser', 'parser_execution_failed')
        notify('failure', category=category, code=code)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
