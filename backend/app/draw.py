import secrets
from uuid import UUID


def draw(ids: list[UUID]) -> dict[UUID, UUID]:
    """Pair every giver with a receiver so that nobody draws themselves.

    Shuffles the receivers and retries on a clash, which keeps every valid pairing
    equally likely.
    """
    if len(ids) < 2:
        raise ValueError("at least 2 participants are required")
    if len(set(ids)) != len(ids):
        # Duplicates could make a self-free pairing impossible and loop forever.
        raise ValueError("participant ids must be unique")
    rng = secrets.SystemRandom()
    receivers = list(ids)
    while True:
        rng.shuffle(receivers)
        if all(giver != receiver for giver, receiver in zip(ids, receivers, strict=True)):
            return dict(zip(ids, receivers, strict=True))
