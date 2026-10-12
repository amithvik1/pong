"""Make SIGTERM behave like Ctrl-C so processes started by the experiment scripts
can be stopped cleanly (log files flushed, LEAVE sent)."""
import signal


def exit_on_signals() -> None:
    def handler(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handler)
    # Also re-enables Ctrl-C if this process inherited "ignore SIGINT"
    # (which happens for background jobs started by a non-interactive shell).
    signal.signal(signal.SIGINT, handler)
