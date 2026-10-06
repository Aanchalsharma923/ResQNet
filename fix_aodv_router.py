import re

with open('resqnet/backend/app/routing/aodv_router.py', 'r') as f:
    content = f.read()

# Replace handle_packet
new_handle_packet = """    def handle_packet(self, packet: Packet) -> list[str]:
        \"\"\"
        Process an incoming packet and determine where it should be forwarded.
        \"\"\"
        if packet.packet_type.name == "RREQ":
            return self._handle_rreq(packet)
        elif packet.packet_type.name == "RREP":
            return self._handle_rrep(packet)
        elif packet.packet_type.name == "RERR":
            return self._handle_rerr(packet)
        else:
            return self._handle_data(packet)"""
content = re.sub(
    r'    def handle_packet\(self, packet: Packet\) -> list\[str\]:.*?(?=    def _handle_rreq)',
    new_handle_packet + "\n\n",
    content,
    flags=re.DOTALL
)

# Append new methods
new_methods = """
    def _handle_data(self, packet: Packet) -> list[str]:
        next_hop = self.get_next_hop(packet.destination_id)
        
        if next_hop:
            my_node = self.topology.get_node_by_id(self.node_id)
            active_neighbors = [n.node_id for n in self.topology.get_active_neighbors(my_node.ip_address)]
            
            if next_hop not in active_neighbors:
                self._generate_rerr(next_hop)
                return []
                
            return [next_hop]
            
        if self.node_id != packet.source_id:
            from resqnet.backend.app.models.aodv_payloads import RERRPayload
            from resqnet.backend.app.models.packet import PacketType
            
            route = self.routing_table.get_route(packet.destination_id)
            seq_num = route.sequence_number if route else 0
            
            rerr_payload = RERRPayload(unreachable_destinations=[(packet.destination_id, seq_num)])
            rerr_packet = Packet(
                source_id=self.node_id,
                destination_id="BROADCAST",
                payload=rerr_payload,
                packet_type=PacketType.RERR
            )
            self.generated_packets.append(rerr_packet)
            self.events.append(f"RERR_GENERATED: node={self.node_id}")
            
        return []

    def _generate_rerr(self, unreachable_next_hop: str):
        affected_dests = []
        for dest_id, route in self.routing_table._routes.items():
            if route.next_hop == unreachable_next_hop and route.is_valid:
                route.sequence_number += 1
                route.invalidate()
                affected_dests.append((dest_id, route.sequence_number))
                self.events.append(f"ROUTE_INVALIDATED: node={self.node_id} dest={dest_id}")
                
        if not affected_dests:
            return
            
        from resqnet.backend.app.models.aodv_payloads import RERRPayload
        from resqnet.backend.app.models.packet import PacketType
        
        rerr_payload = RERRPayload(unreachable_destinations=affected_dests)
        rerr_packet = Packet(
            source_id=self.node_id,
            destination_id="BROADCAST",
            payload=rerr_payload,
            packet_type=PacketType.RERR
        )
        self.generated_packets.append(rerr_packet)
        self.events.append(f"RERR_GENERATED: node={self.node_id}")

    def _handle_rerr(self, packet: Packet) -> list[str]:
        from resqnet.backend.app.models.aodv_payloads import RERRPayload
        payload: RERRPayload = packet.payload
        
        affected = False
        prev_hop = packet.route_history[-2] if len(packet.route_history) >= 2 else None
        is_source = (self.node_id == packet.source_id and len(packet.route_history) == 1)
        
        if not is_source:
            for dest, seq_num in payload.unreachable_destinations:
                route = self.routing_table.get_route(dest)
                if route and route.is_valid:
                    if prev_hop and route.next_hop == prev_hop:
                        route.sequence_number = max(route.sequence_number, seq_num)
                        route.invalidate()
                        affected = True
                        self.events.append(f"ROUTE_INVALIDATED: node={self.node_id} dest={dest}")
                        
        if is_source or affected:
            my_node = self.topology.get_node_by_id(self.node_id)
            active_neighbors = [n.node_id for n in self.topology.get_active_neighbors(my_node.ip_address)]
            
            next_hops = []
            for neighbor in active_neighbors:
                if neighbor != prev_hop:
                    next_hops.append(neighbor)
            return next_hops
            
        return []
