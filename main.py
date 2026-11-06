import asyncio
import sys

from config import APP_NAME, APP_VERSION
from core.session import create_session
from core.messenger import Messenger


async def main():
    print("=" * 44)
    print(f"       {APP_NAME} v{APP_VERSION}")
    print("       FACEBOOK GROUP CONTROL")
    print("=" * 44)

    messenger = None
    exit_code = 0

    try:
        print("\n[1] Initializing session...")

        session = await create_session()

        if not session:
            print("[-] Session initialization failed.")
            exit_code = 1
            return exit_code

        print("[+] Facebook session initialized.")

        print("\n[2] Initializing Messenger...")

        messenger = Messenger(session)

        print("[+] Messenger initialized.")
        print("\n[3] Starting listener...")
        print("[*] Press CTRL+C to stop.\n")

        await messenger.start()

    except KeyboardInterrupt:
        print("\n[!] Stopping application.")

    except Exception as error:
        print(f"[-] {type(error).__name__}: {error}")
        exit_code = 1

    finally:
        if messenger:
            try:
                await messenger.stop()
            except Exception as error:
                print(f"[-] Cleanup error: {type(error).__name__}: {error}")
                exit_code = 1

        print("\n[*] Application closed.")

    return exit_code


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exit.")
        code = 0

    sys.exit(code)
