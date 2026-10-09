import argparse
import asyncio
import json
import sys
import webbrowser
from .config import Config


def main():
    parser = argparse.ArgumentParser(description="June personal AI operating layer")
    parser.add_argument("command", nargs="?", choices=["desktop", "serve", "chat", "doctor", "dashboard", "vault"], default="desktop")
    parser.add_argument("--root", default=None)
    parser.add_argument("--name", help="Credential name for vault command")
    parser.add_argument("--minimized", action="store_true", help="Start in the tray without a large window")
    args = parser.parse_args()
    config = Config.load(args.root)
    if args.minimized:
        config.start_minimized = True
    if args.command == "vault":
        from getpass import getpass
        from .security import Vault
        if not args.name:
            parser.error("vault requires --name")
        Vault(config.root).set(args.name, getpass("Secret (stored in Windows Credential Manager): "))
        print("Credential saved; value not displayed.")
        return
    if args.command == "dashboard":
        token_path = config.root / "data/api-token"
        if not token_path.exists():
            sys.exit("Start June desktop or serve first")
        webbrowser.open(f"http://127.0.0.1:{config.port}/#" + token_path.read_text().strip())
        return
    from .runtime import Runtime
    runtime = Runtime(config)
    if args.command == "desktop":
        from .desktop import launch
        launch(runtime)
    elif args.command == "serve":
        import uvicorn
        from .api import create_app
        server = uvicorn.Server(uvicorn.Config(create_app(runtime), host="127.0.0.1", port=config.port, access_log=False))
        runtime.shutdown_handler = lambda: setattr(server, "should_exit", True)
        server.run()
    elif args.command == "doctor":
        async def doctor():
            print(json.dumps(await runtime.health(), indent=2))
            await runtime.close()
        asyncio.run(doctor())
    else:
        async def chat():
            await runtime.start()
            print("June. Type /quit to exit, /privacy to disable connections.")
            try:
                while True:
                    text = await asyncio.to_thread(input, "Mayank> ")
                    if text == "/quit":
                        break
                    if text == "/privacy":
                        await runtime.settings({"privacy": True})
                        continue
                    job = runtime.submit(text, "terminal")
                    while job["id"] in runtime.jobs:
                        pending = [a for a in runtime.store.list("approval") if a["status"] == "pending"]
                        for a in pending:
                            print(f"Approval level {a['risk']} — {a['tool']}\n{a['parameters']}")
                            answer = await asyncio.to_thread(input, "Approve this exact action? [yes/no/cancel] ")
                            if answer == "cancel":
                                await runtime.cancel(job["id"])
                            else:
                                runtime.approve(a["id"], answer.lower() == "yes")
                        await asyncio.sleep(.2)
                    result = runtime.store.get("job", job["id"])
                    print("June>", result.get("response", result.get("error", result["status"])))
                    if runtime.shutdown_requested:
                        break
            finally:
                await runtime.close()
        asyncio.run(chat())


if __name__ == "__main__":
    main()
