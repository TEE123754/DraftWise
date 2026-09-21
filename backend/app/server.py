import asyncio

import uvicorn


def main() -> None:
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
