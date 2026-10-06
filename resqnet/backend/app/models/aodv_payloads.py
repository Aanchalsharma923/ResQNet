class RREQPayload:
    """
    Payload for an AODV Route Request (RREQ) control message.
    """
    def __init__(
        self,
        source_id: str,
        destination_id: str,
        source_sequence_number: int,
        destination_sequence_number: int,
        broadcast_id: int,
        hop_count: int
    ):
        if not source_id or not destination_id:
            raise ValueError("source_id and destination_id are required")
        if source_sequence_number < 0 or destination_sequence_number < 0:
            raise ValueError("Sequence numbers must be non-negative")
        if broadcast_id < 0:
            raise ValueError("broadcast_id must be non-negative")
        if hop_count < 0:
            raise ValueError("hop_count must be non-negative")

        self.source_id = source_id
        self.destination_id = destination_id
        self.source_sequence_number = source_sequence_number
        self.destination_sequence_number = destination_sequence_number
        self.broadcast_id = broadcast_id
        self.hop_count = hop_count

    @property
    def identity(self) -> tuple[str, int]:
        """
        Returns the unique tuple identity of the RREQ (source_id, broadcast_id)
        used for duplicate detection.
        """
        return (self.source_id, self.broadcast_id)


class RREPPayload:
    """
    Payload for an AODV Route Reply (RREP) control message.
    """
    def __init__(
        self,
        destination_id: str,
        destination_sequence_number: int,
        originator_id: str,
        hop_count: int
    ):
        if not destination_id or not originator_id:
            raise ValueError("destination_id and originator_id are required")
        if destination_sequence_number < 0:
            raise ValueError("Sequence numbers must be non-negative")
        if hop_count < 0:
            raise ValueError("hop_count must be non-negative")

        self.destination_id = destination_id
        self.destination_sequence_number = destination_sequence_number
        self.originator_id = originator_id
        self.hop_count = hop_count

class RERRPayload:
    """
    Payload for an AODV Route Error (RERR) control message.
    """
    def __init__(
        self,
        unreachable_destinations: list[tuple[str, int]]
    ):
        if not unreachable_destinations:
            raise ValueError("Must provide at least one unreachable destination")
        
        # List of (destination_id, destination_sequence_number)
        self.unreachable_destinations = unreachable_destinations
