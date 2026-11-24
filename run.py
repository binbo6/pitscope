import argparse
import logging

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='PitScope 本地工程知识助手')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--demo',action='store_true',help='生成示范报告，不启动服务')
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.demo:
        from scripts.build_case import main
        main(offline=args.offline)
    else:
        import uvicorn
        if args.open_browser:
            import threading, time, urllib.request, webbrowser
            def open_when_ready():
                for _ in range(40):
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/status',timeout=1) as response:
                            if response.status==200:
                                webbrowser.open(f'http://127.0.0.1:{args.port}');return
                    except Exception:time.sleep(.5)
            threading.Thread(target=open_when_ready,daemon=True).start()
        print(f'PitScope: http://127.0.0.1:{args.port}',flush=True)
        uvicorn.run('pit.server:app',host='127.0.0.1',port=args.port,log_level='info')
