import pytest
from resqnet.backend.app.routing.table import RouteEntry, RoutingTable

def test_entry_creation():
    """Test 1 - Entry creation"""
    entry = RouteEntry(
        destination_id="H",
        next_hop="B",
        hop_count=3,
        sequence_number=5,
        is_valid=True
    )
    assert entry.destination_id == "H"
    assert entry.next_hop == "B"
    assert entry.hop_count == 3
    assert entry.sequence_number == 5
    assert entry.is_valid is True

def test_table_insertion_and_lookup():
    """Test 2 & 3 - Table insertion and Lookup"""
    table = RoutingTable()
    added = table.add_or_update_route("H", "B", 3, 5)
    assert added is True
    
    entry = table.get_route("H")
    assert entry is not None
    assert entry.destination_id == "H"

def test_next_hop_correctness():
    """Test 4 - Next-hop correctness"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    entry = table.get_route("H")
    assert entry.next_hop == "B"

def test_hop_count():
    """Test 5 - Hop count"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    entry = table.get_route("H")
    assert entry.hop_count == 3

def test_sequence_number():
    """Test 6 - Sequence number"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    entry = table.get_route("H")
    assert entry.sequence_number == 5

def test_validity():
    """Test 7 - Validity"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    entry = table.get_route("H")
    assert entry.is_valid is True

def test_invalidation():
    """Test 8 - Invalidation"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    table.invalidate_route("H")
    entry = table.get_route("H")
    assert entry is not None
    assert entry.is_valid is False

def test_route_update():
    """Test 9 - Route update"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    # Same sequence number, but lower hop count -> should update
    updated = table.add_or_update_route("H", "C", 2, 5)
    assert updated is True
    
    entry = table.get_route("H")
    assert entry.next_hop == "C"
    assert entry.hop_count == 2
    assert entry.sequence_number == 5
    
    # Higher sequence number -> should update even if hop count is worse
    updated2 = table.add_or_update_route("H", "D", 4, 6)
    assert updated2 is True
    
    entry2 = table.get_route("H")
    assert entry2.next_hop == "D"
    assert entry2.hop_count == 4
    assert entry2.sequence_number == 6

def test_stale_route_protection():
    """Test 10 - Stale route protection"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    # Lower sequence number -> should NOT update
    updated = table.add_or_update_route("H", "E", 1, 4)
    assert updated is False
    
    entry = table.get_route("H")
    assert entry.next_hop == "B"
    assert entry.hop_count == 3
    assert entry.sequence_number == 5
    
    # Same sequence number, but worse or equal hop count -> should NOT update
    updated2 = table.add_or_update_route("H", "F", 4, 5)
    assert updated2 is False
    updated3 = table.add_or_update_route("H", "G", 3, 5)
    assert updated3 is False
    
    entry2 = table.get_route("H")
    assert entry2.next_hop == "B"

def test_next_hop_versus_full_path():
    """Test 11 - Next-hop versus full path"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    
    entry = table.get_route("H")
    # Asserting it's just a single string identifier, not a list
    assert isinstance(entry.next_hop, str)
    assert entry.next_hop == "B"
    assert entry.next_hop != "['A', 'B', 'C', 'H']"

def test_multiple_destinations():
    """Test 12 - Multiple destinations"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    table.add_or_update_route("C", "B", 1, 2)
    table.add_or_update_route("D", "D", 0, 10)
    
    h_entry = table.get_route("H")
    c_entry = table.get_route("C")
    d_entry = table.get_route("D")
    
    assert h_entry.next_hop == "B"
    assert h_entry.destination_id == "H"
    
    assert c_entry.next_hop == "B"
    assert c_entry.destination_id == "C"
    
    assert d_entry.next_hop == "D"
    assert d_entry.destination_id == "D"

def test_invalid_route_update():
    """Extra Test - Updating an invalid route with a new route having same sequence number"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    table.invalidate_route("H")
    
    assert table.get_route("H").is_valid is False
    
    # Should update because the existing route is invalid, even with equal sequence number and worse hop count
    updated = table.add_or_update_route("H", "C", 4, 5)
    assert updated is True
    
    entry = table.get_route("H")
    assert entry.is_valid is True
    assert entry.next_hop == "C"
    assert entry.hop_count == 4

def test_remove_route():
    """Extra Test - Removing a route entirely"""
    table = RoutingTable()
    table.add_or_update_route("H", "B", 3, 5)
    assert table.get_route("H") is not None
    
    table.remove_route("H")
    assert table.get_route("H") is None
