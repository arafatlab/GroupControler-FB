import asyncio

from config import APP_NAME, APP_VERSION
from core.session import create_session
from core.messenger import Messenger


async def main():
    print("=" * 44)
    print(f"       {APP_NAME} v{APP_VERSION}")
    print("       FACEBOOK GROUP CONTROL")
    print("=" * 44)

    messenger = None

    try:
        print("\n[1] Initializing session...")

        session = await create_session()

        if not session:
            print("[-] Session initialization failed.")
            return

        print("[+] Facebook session initialized.")

        print("\n[2] Initializing Messenger...")

        messenger = Messenger(session)

        print("[+] Messenger initialized.")

        print("\n[3] Starting listener...")
        print("[*] Press CTRL+C to stop.\n")

        await messenger.start()

    except FileNotFoundError as error:
        print(f"[-] {error}")

    except KeyboardInterrupt:
        print("\n[!] Stopping application...")

    except Exception as error:
        print(f"[-] {type(error).__name__}: {error}")

    finally:
        if messenger:
            await messenger.stop()

        print("\n[*] Application closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Exit.")
