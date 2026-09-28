"""Keep a completed fresh child alive until its owner brackets the exit."""
import os
import runpy
import socket
import sys
import traceback


def main():
    module = sys.argv[1]
    sys.argv = [module, *sys.argv[2:]]
    code = 0
    try:
        runpy.run_module(module, run_name='__main__', alter_sys=True)
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else int(error.code is not None)
    except BaseException:
        traceback.print_exc()
        code = 1
    with socket.socket(fileno=int(os.environ['PDF_PROCESS_LIFECYCLE_FD'])) as control:
        control.sendall(b'1')
        if control.recv(1) != b'1':
            code = code or 1
    raise SystemExit(code)


if __name__ == '__main__':
    main()
