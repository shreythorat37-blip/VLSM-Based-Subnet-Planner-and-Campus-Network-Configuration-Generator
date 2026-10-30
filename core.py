"""Core logic for CampusNet Studio: VLSM planning, Cisco config generation and queue simulation."""
from __future__ import annotations
import ipaddress, math, random, re
from collections import deque
from typing import Any


def plan_vlsm(base_cidr: str, departments: list[dict[str, Any]]) -> dict[str, Any]:
    """Allocate non-overlapping VLSM subnets within an IPv4 private base network."""
    try:
        base = ipaddress.ip_network(base_cidr.strip(), strict=False)
    except Exception as exc:
        raise ValueError(f"Invalid IPv4 network: {exc}") from exc
    if not isinstance(base, ipaddress.IPv4Network):
        raise ValueError("Only IPv4 networks are supported.")
    rfc1918 = [ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'), ipaddress.ip_network('192.168.0.0/16')]
    if not any(base.subnet_of(private) for private in rfc1918):
        raise ValueError("Choose an RFC 1918 private IPv4 block (10/8, 172.16/12 or 192.168/16).")
    if not departments:
        raise ValueError("Add at least one department.")
    normalized=[]; seen=set()
    for d in departments:
        name=str(d.get('name','')).strip()
        raw_hosts=d.get('hosts',0)
        if isinstance(raw_hosts, bool):
            raise ValueError(f"Host count for {name or 'department'} must be a whole number.")
        try:
            hosts=int(raw_hosts)
            if str(raw_hosts).strip() != str(hosts): raise ValueError
        except Exception:
            raise ValueError(f"Host count for {name or 'department'} must be a whole number.") from None
        if not name: raise ValueError("Department names cannot be blank.")
        if name.lower() in seen: raise ValueError(f"Duplicate department name: {name}")
        seen.add(name.lower())
        if hosts < 1: raise ValueError(f"Host count for {name} must be at least 1.")
        if hosts > 2**24-2: raise ValueError(f"Host count for {name} is too large for a conventional IPv4 subnet.")
        # This project follows conventional subnetting and reserves network + broadcast.
        prefix=32
        while prefix > 0 and (2**(32-prefix)-2) < hosts: prefix-=1
        if prefix < 0 or prefix == 0: raise ValueError(f"Unable to size subnet for {name}.")
        normalized.append({'name':name,'hosts':hosts,'prefix':prefix})
    normalized.sort(key=lambda x:(-x['hosts'],x['name'].lower()))
    cursor=int(base.network_address); end=int(base.broadcast_address); rows=[]
    for d in normalized:
        size=2**(32-d['prefix'])
        start=((cursor+size-1)//size)*size
        last=start+size-1
        if last > end:
            raise ValueError(f"Base block {base} is too small. Cannot allocate {d['name']} (needs /{d['prefix']}).")
        net=ipaddress.ip_network((start,d['prefix']))
        hosts_list=list(net.hosts())
        first=hosts_list[0] if hosts_list else net.network_address
        last_host=hosts_list[-1] if hosts_list else net.broadcast_address
        rows.append({
            'Department':d['name'],'Hosts Required':d['hosts'],'VLAN':10+10*len(rows),
            'Network/CIDR':str(net),'Prefix':f"/{net.prefixlen}",'Subnet Mask':str(net.netmask),
            'Total Addresses':net.num_addresses,'Usable Hosts':max(net.num_addresses-2,0),
            'First Usable':str(first),'Last Usable':str(last_host),'Broadcast':str(net.broadcast_address),
            'Gateway':str(first),'Unused Usable':max(net.num_addresses-2-d['hosts'],0),
            'Utilization %':round(d['hosts']/max(net.num_addresses-2,1)*100,2)
        })
        cursor=last+1
    used=sum(r['Total Addresses'] for r in rows)
    total_usable=sum(r['Usable Hosts'] for r in rows)
    required=sum(r['Hosts Required'] for r in rows)
    fixed_addresses=len(rows)*256 if all(r['Hosts Required'] <= 254 for r in rows) else None
    fixed_usable=len(rows)*254 if fixed_addresses is not None else None
    remaining_blocks = [str(n) for n in ipaddress.summarize_address_range(ipaddress.IPv4Address(cursor), base.broadcast_address)] if cursor <= end else []
    return {'base':str(base),'rows':rows,'departments':len(rows),'required_hosts':required,
            'allocated_addresses':used,'allocated_usable':total_usable,'remaining_addresses':base.num_addresses-used,
            'remaining_blocks':remaining_blocks,
            'base_addresses':base.num_addresses,'vlsm_waste_pct':round((total_usable-required)/max(total_usable,1)*100,2),
            'fixed_addresses':fixed_addresses,'fixed_usable':fixed_usable,
            'fixed_waste_pct':round((fixed_usable-required)/max(fixed_usable,1)*100,2) if fixed_usable is not None else None,
            'address_savings':fixed_addresses-used if fixed_addresses is not None else None}


def generate_router_config(plan: dict[str, Any], interface: str='GigabitEthernet0/0', dns: str='8.8.8.8', nat: bool=False, ospf: bool=False) -> str:
    interface=str(interface).strip()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9./-]{0,63}', interface): raise ValueError('Router interface contains unsupported characters.')
    try: dns=str(ipaddress.IPv4Address(str(dns).strip()))
    except Exception: raise ValueError('DNS server must be a valid IPv4 address.') from None
    lines=['! Generated by CampusNet Studio','! Review interface names, VLAN IDs, routing and platform syntax before deployment.','configure terminal','']
    for r in plan['rows']:
        lines += [f"interface {interface}.{r['VLAN']}",f" description {r['Department']} VLAN {r['VLAN']}",f" encapsulation dot1Q {r['VLAN']}",f" ip address {r['Gateway']} {r['Subnet Mask']}",' no shutdown',' exit','']
    lines += ['! DHCP pools']
    for r in plan['rows']:
        lines += [f"ip dhcp excluded-address {r['Gateway']}",f"ip dhcp pool {re.sub(r'[^A-Za-z0-9_-]','_',r['Department'])[:32]}",f" network {r['Network/CIDR'].split('/')[0]} {r['Subnet Mask']}",f" default-router {r['Gateway']}",f" dns-server {dns}",' exit','']
    if ospf:
        lines += ['! Example OSPF starter; verify wildcard masks and process design for your topology','router ospf 1',' router-id 1.1.1.1']
        for r in plan['rows']:
            net=ipaddress.ip_network(r['Network/CIDR'])
            wildcard=ipaddress.IPv4Address(int(ipaddress.IPv4Address('255.255.255.255'))-int(net.netmask))
            lines.append(f" network {net.network_address} {wildcard} area 0")
        lines += [' exit','']
    if nat:
        lines += ['! NAT overload requires correct inside/outside interface roles and an upstream route.','! Example ACL; adjust to your edge-router design.',f"access-list 10 permit {ipaddress.ip_network(plan['base']).network_address} {ipaddress.IPv4Address(0xFFFFFFFF-int(ipaddress.ip_network(plan['base']).netmask))}",'! ip nat inside source list 10 interface <WAN_INTERFACE> overload','! Apply ip nat inside/outside to the correct interfaces.','']
    lines += ['end','write memory','']
    return '\n'.join(lines)


def generate_switch_config(plan: dict[str, Any], trunk_port: str='GigabitEthernet0/1') -> str:
    trunk_port=str(trunk_port).strip()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9./-]{0,63}', trunk_port): raise ValueError('Switch trunk port contains unsupported characters.')
    lines=['! Generated by CampusNet Studio','configure terminal']
    for r in plan['rows']:
        lines += [f"vlan {r['VLAN']}",f" name {''.join(c if c.isalnum() else '_' for c in r['Department']).upper()}",' exit']
    lines += [f'interface {trunk_port}',' description Trunk to router',' switchport mode trunk',' no shutdown',' exit','! Assign access ports to VLANs based on your physical topology.']
    for i,r in enumerate(plan['rows']):
        port=f'FastEthernet0/{i+1}'
        lines += [f'interface {port}',f" description {r['Department']} endpoint port",' switchport mode access',f" switchport access vlan {r['VLAN']}",' spanning-tree portfast',' no shutdown',' exit']
    lines += ['end','write memory','']
    return '\n'.join(lines)


def simulate_queue(algorithm='DropTail', duration=20.0, arrival_rate=800.0, bandwidth_mbps=5.0, queue_limit=50,
                   packet_size_bytes=1000, seed=7, red_min=10, red_max=30, link_delay_ms=2.0) -> dict[str, Any]:
    """Packet-level discrete event queue simulation; arrivals are Poisson, service time is packet bits / link rate."""
    if algorithm not in ('DropTail','RED'): raise ValueError('algorithm must be DropTail or RED')
    if duration <= 0 or arrival_rate < 0 or bandwidth_mbps <= 0 or queue_limit < 1 or packet_size_bytes < 1:
        raise ValueError('Duration, bandwidth, queue limit and packet size must be positive; load cannot be negative.')
    if algorithm=='RED' and not (0 <= red_min < red_max <= queue_limit): raise ValueError('RED thresholds must satisfy 0 <= min < max <= queue limit.')
    rng=random.Random(seed)
    # Generate arrivals using exponential inter-arrival times.
    arrivals=[]; t=0.0
    if arrival_rate:
        while True:
            t += rng.expovariate(arrival_rate)
            if t > duration: break
            arrivals.append(t)
    q=deque(); next_departure=0.0; delivered=[]; dropped=0; red_drops=0; tail_drops=0
    avg_q=0.0; ewma=0.0; wq=0.002; snapshots=[]; idx=0; clock=0.0
    # Process each arrival and drain queue as time advances.
    for at in arrivals:
        while q and next_departure <= at:
            pkt=q.popleft(); dep=next_departure
            delivered.append((pkt,dep))
            if q: next_departure += (packet_size_bytes*8)/(bandwidth_mbps*1_000_000)
            else: next_departure=dep
        clock=at
        qlen=len(q); ewma=(1-wq)*ewma+wq*qlen
        drop=False
        if algorithm=='RED':
            if ewma >= red_max: drop=True
            elif ewma > red_min:
                probability=min(1.0,(ewma-red_min)/max(red_max-red_min,1))
                drop=rng.random()<probability
        if drop:
            dropped+=1; red_drops+=1
        elif len(q)>=queue_limit:
            dropped+=1; tail_drops+=1
        else:
            q.append(at)
            if len(q)==1:
                next_departure=max(at,next_departure)+(packet_size_bytes*8)/(bandwidth_mbps*1_000_000)
        avg_q += len(q)
        if len(snapshots)<500 and (len(arrivals)<500 or idx%max(1,len(arrivals)//500)==0): snapshots.append({'time_s':at,'queue_packets':len(q)})
        idx+=1
    while q:
        pkt=q.popleft(); dep=next_departure
        if dep <= duration:
            delivered.append((pkt,dep))
        else:
            # In-flight/queued packets at the observation boundary count as not delivered yet.
            dropped += 1
        next_departure=dep+(packet_size_bytes*8)/(bandwidth_mbps*1_000_000) if q else dep
    received=len(delivered); sent=len(arrivals); lost=max(sent-received,0)
    delays=[(dep-at)*1000 for at,dep in delivered]
    bits=received*packet_size_bytes*8
    return {'algorithm':algorithm,'duration_s':duration,'arrival_rate_pps':arrival_rate,'bandwidth_mbps':bandwidth_mbps,
            'queue_limit_packets':queue_limit,'packet_size_bytes':packet_size_bytes,'packets_sent':sent,
            'packets_received':received,'packets_lost':lost,'packet_loss_pct':round(lost/max(sent,1)*100,3),
            'delivery_ratio_pct':round(received/max(sent,1)*100,3),'throughput_mbps':round(bits/duration/1_000_000,4),
            'avg_delay_ms':round(sum(delays)/max(len(delays),1),4),'avg_queue_packets':round(avg_q/max(sent,1),3),
            'red_early_drops':red_drops,'tail_drops':tail_drops,'queue_samples':snapshots,
            'assumptions':'Poisson arrivals; FIFO queue; constant packet size; service time = packet bits / configured link bandwidth; fixed propagation delay is configurable but excluded from queue delay metric.'}
