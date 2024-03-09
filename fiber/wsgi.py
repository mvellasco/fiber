from fiber import core

application = core.create_app()


if __name__ == "__main__":
    import bjoern

    bjoern.run(application, "0.0.0.0", 8000)
