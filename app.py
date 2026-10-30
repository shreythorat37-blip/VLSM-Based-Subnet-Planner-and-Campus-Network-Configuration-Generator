from __future__ import annotations
import json, io, csv, time, shutil
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from core import plan_vlsm, generate_router_config, generate_switch_config, simulate_queue

st.set_page_config(page_title='CampusNet Studio', page_icon='🌐', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
:root{--ink:#12243a;--muted:#62748a;--blue:#2b6cb0;--cyan:#27c2b8;--line:#dce6f1;}
.block-container{padding-top:1.2rem;padding-bottom:2rem;max-width:1500px}
.hero{padding:1.6rem 1.8rem;border-radius:22px;background:linear-gradient(115deg,#10243e 0%,#174c70 56%,#177f83 100%);color:white;margin-bottom:1rem;box-shadow:0 12px 35px #183c5c22}
.hero h1{font-size:2.15rem;line-height:1.18;margin:0 0 .45rem 0;color:white}.hero p{font-size:1.03rem;color:#dbeafe;margin:.15rem 0}
.eyebrow{font-size:.74rem;letter-spacing:.18em;font-weight:800;text-transform:uppercase;color:#a7f3d0;margin-bottom:.55rem}
.pill{display:inline-block;border:1px solid #b8d8e9;border-radius:999px;padding:.28rem .7rem;margin:.25rem .25rem 0 0;font-size:.78rem;color:#eafaff;background:#ffffff10}
.section{font-size:1.28rem;font-weight:750;color:#17324d;margin:.35rem 0 .6rem}
.small-muted{color:#64748b;font-size:.9rem}.metric-note{font-size:.8rem;color:#64748b}
div[data-testid="stMetric"]{color:#12243a;background:#f5f9fd;border:1px solid #e2eaf3;padding:13px 15px;border-radius:15px}div[data-testid="stMetric"] *{color:#12243a !important}
.stTabs [data-baseweb="tab-list"]{gap:8px}.stTabs [data-baseweb="tab"]{border-radius:9px;padding:9px 15px;background:#f1f6fb}
[data-testid="stSidebar"]{border-right:1px solid #e2e8f0}
</style>''',unsafe_allow_html=True)

st.markdown('''<div class="hero"><div class="eyebrow">COMPUTER NETWORKS • INTEGRATED PROJECT</div><h1>VLSM-Based Subnet Planner and Configuration Generator</h1><p>Simulated Campus Network Implementation · Address planning · Cisco configuration · Performance lab</p><span class="pill">VLSM / CIDR</span><span class="pill">VLAN · DHCP · NAT · OSPF/RIP</span><span class="pill">DropTail vs RED</span><span class="pill">Packet-size study</span></div>''',unsafe_allow_html=True)

with st.sidebar:
    st.markdown('## 🌐 CampusNet Studio')
    st.caption('Integrated project workspace')
    page=st.radio('Workspace', ['Overview','VLSM Planner','Configuration Generator','Campus Network Design','Performance Lab','CLI & External Tools','Testing & Results','Project Documentation'],label_visibility='visible')
    st.divider()
    st.markdown('**Project team**')
    st.write('Arihant Singi · 24BCT0305')
    st.write('Shrey Thorat · 24BCB0067')
    st.divider()
    st.caption('Educational simulation. Validate generated configurations before using real devices.')

DEFAULT_DEPTS=[{'Department':'CSE','Hosts':120},{'Department':'ECE','Hosts':120},{'Department':'Library','Hosts':60},{'Department':'Administration','Hosts':60},{'Department':'Hostel','Hosts':45}]
if 'dept_df' not in st.session_state: st.session_state.dept_df=pd.DataFrame(DEFAULT_DEPTS)
if 'base_cidr' not in st.session_state: st.session_state.base_cidr='192.168.0.0/23'
if 'plan' not in st.session_state: st.session_state.plan=None

def compute_plan():
    records=st.session_state.dept_df.rename(columns={'Department':'name','Hosts':'hosts'}).to_dict('records')
    st.session_state.plan=plan_vlsm(st.session_state.base_cidr,records)

def get_plan():
    if st.session_state.plan is None:
        try: compute_plan()
        except Exception: return None
    return st.session_state.plan

def kpi(label,value,helptext=None): st.metric(label,value,help=helptext)

if page=='Overview':
    st.markdown('<div class="section">Project command center</div>',unsafe_allow_html=True)
    st.write('A unified workspace that connects the report’s four stages: address planning, Cisco configuration generation, simulated campus design, and quantitative network-performance experiments.')
    try: p=get_plan()
    except Exception as e: p=None; st.warning(f'Calculate the sample plan in VLSM Planner to see live summary: {e}')
    c1,c2,c3,c4=st.columns(4)
    with c1: kpi('Project modules','4','Planner, configuration, campus design, performance and evaluation')
    with c2: kpi('Sample departments','5','CSE, ECE, Library, Administration, Hostel')
    with c3: kpi('Sample host demand','405','Illustrative values from the project review document')
    with c4: kpi('Private base block','/23','192.168.0.0/23 sample plan')
    st.divider()
    left,right=st.columns([1.1,.9])
    with left:
        st.markdown('### System workflow')
        flow=[('01','Plan','Enter private base block and department host demand.'),('02','Validate','Size subnets, prevent overlap, confirm capacity.'),('03','Generate','Export router subinterfaces, DHCP pools and switch VLAN config.'),('04','Implement','Apply reviewed configuration in Cisco Packet Tracer.'),('05','Evaluate','Use connectivity tests and queue/packet-size experiments.')]
        for n,title,desc in flow:
            st.markdown(f'**{n} · {title}**  \n<span class="small-muted">{desc}</span>',unsafe_allow_html=True)
    with right:
        st.markdown('### Deliverables checklist')
        for item in ['VLSM subnet plan + CSV/JSON export','Overlap/capacity validation','Cisco IOS router and switch config templates','DHCP pool generation','Address utilization comparison','DropTail vs RED congestion experiment','Packet-size performance experiment','Test matrix, report notes and NS2 starter files']:
            st.markdown('✓ '+item)
    st.info('The report specifies NS2/NAM as the target network-simulation environment. The included Performance Lab is a Python packet-queue model for reproducible experiments; it is not an NS2 run and should not be presented as measured NS2 output.')

elif page=='VLSM Planner':
    st.markdown('<div class="section">VLSM planner & validator</div>',unsafe_allow_html=True)
    st.write('Allocate the smallest conventional IPv4 subnet that satisfies each department’s host requirement. Largest departments are allocated first.')
    with st.form('planner_form'):
        st.text_input('Private base network (CIDR)',key='base_cidr',help='Example: 192.168.0.0/23. Use RFC 1918 private IPv4 address space.')
        st.caption('Edit department names and host counts below. Add or remove rows directly in the table.')
        edited=st.data_editor(st.session_state.dept_df,num_rows='dynamic',use_container_width=True,key='dept_editor',column_config={'Department':st.column_config.TextColumn(required=True),'Hosts':st.column_config.NumberColumn(min_value=1,step=1,required=True)},hide_index=True)
        submitted=st.form_submit_button('⚡ Calculate & validate plan',type='primary',use_container_width=True)
    if submitted:
        st.session_state.dept_df=edited
        try:
            rec=edited.rename(columns={'Department':'name','Hosts':'hosts'}).to_dict('records')
            st.session_state.plan=plan_vlsm(st.session_state.base_cidr,rec)
            st.success('Plan allocated and validated: no overlap, every subnet is inside the base block, and all departments have enough usable addresses.')
        except Exception as e: st.session_state.plan=None; st.error(str(e))
    p=get_plan()
    if p:
        st.divider(); a,b,c,d=st.columns(4)
        with a:kpi('Required hosts',f"{p['required_hosts']:,}")
        with b:kpi('VLSM address allocation',f"{p['allocated_addresses']:,}")
        with c:kpi('Addresses remaining',f"{p['remaining_addresses']:,}")
        with d:kpi('Fixed-/24 addresses',f"{p['fixed_addresses']:,}")
        df=pd.DataFrame(p['rows'])
        st.markdown('### Allocation table')
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.markdown('### Fixed /24 vs VLSM')
        cm1,cm2,cm3=st.columns(3)
        with cm1:kpi('Address reduction',f"{p['address_savings']:,}", 'Fixed /24 allocation minus VLSM allocation')
        with cm2:kpi('VLSM unused usable capacity',f"{p['vlsm_waste_pct']}%")
        with cm3:kpi('Fixed /24 unused usable capacity',f"{p['fixed_waste_pct']}%")
        chart=pd.DataFrame({'Method':['Fixed /24','VLSM'],'Allocated addresses':[p['fixed_addresses'],p['allocated_addresses']]})
        fig,ax=plt.subplots(figsize=(7,2.8)); ax.barh(chart['Method'],chart['Allocated addresses']); ax.set_xlabel('IPv4 addresses allocated'); ax.grid(axis='x',alpha=.25); st.pyplot(fig); plt.close(fig)
        st.download_button('Download subnet plan (CSV)',df.to_csv(index=False).encode(),file_name='campus_vlsm_plan.csv',mime='text/csv')
        st.download_button('Download subnet plan (JSON)',json.dumps(p,indent=2).encode(),file_name='campus_vlsm_plan.json',mime='application/json')
        st.caption('The percentage shown is unused usable capacity within the allocated subnets, not unused space in the entire base block. Values are design calculations and should be confirmed against final requirements.')

elif page=='Configuration Generator':
    st.markdown('<div class="section">Cisco configuration generator</div>',unsafe_allow_html=True)
    st.write('Generate reviewable IOS configuration snippets from the current VLSM plan. Templates are starting points, not device-tested configs.')
    p=get_plan()
    if not p: st.warning('Fix the VLSM plan first.'); st.stop()
    c1,c2,c3=st.columns(3)
    with c1: router_if=st.text_input('Router trunk interface','GigabitEthernet0/0')
    with c2: switch_trunk=st.text_input('Switch trunk port','GigabitEthernet0/1')
    with c3: dns=st.text_input('DNS server','8.8.8.8')
    x,y=st.columns(2)
    with x: enable_ospf=st.checkbox('Include OSPF starter commands',value=False)
    with y: include_nat=st.checkbox('Include NAT example notes',value=False)
    router=generate_router_config(p,router_if,dns,include_nat,enable_ospf)
    switch=generate_switch_config(p,switch_trunk)
    t1,t2,t3=st.tabs(['Router + DHCP','Switch VLANs','Deployment checklist'])
    with t1:
        st.code(router,language='text')
        st.download_button('Download router_config.txt',router,file_name='router_config.txt',mime='text/plain')
    with t2:
        st.code(switch,language='text')
        st.download_button('Download switch_config.txt',switch,file_name='switch_config.txt',mime='text/plain')
    with t3:
        for x in ['Confirm router and switch model/interface names.','Check VLAN IDs and access-port assignments against the physical topology.','Review DHCP excluded ranges; reserve any statically assigned infrastructure addresses.','Configure routing between routers separately; OSPF networks and wildcard masks must match the real topology.','For NAT, identify inside/outside interfaces, ACL, default route and ISP addressing.','Apply configuration in Packet Tracer first, then verify with show commands and ping.']:
            st.checkbox(x,key='deploy_'+str(abs(hash(x))))
        st.warning('NAT is intentionally a commented example: a single-router template cannot safely infer WAN interface, ACL scope, default route, or inside/outside roles.')

elif page=='Campus Network Design':
    st.markdown('<div class="section">Campus topology & implementation blueprint</div>',unsafe_allow_html=True)
    st.write('The review document describes an edge router connected to two internal routers, with department VLANs behind R2/R3 and an external ISP/server.')
    st.markdown('''```text
                         [Simulated ISP / Server]
                                  |
                             [R1 Edge]
                         NAT overload / OSPF
                           /             \\
                      /30 P2P           /30 P2P
                        /                 \\
                     [R2]                 [R3]
                Academic LANs       Library / Admin / Hostel
                     |                     |
                802.1Q trunk           802.1Q trunk
                     |                     |
                [Access SW]            [Access SW]
                 VLANs / PCs            VLANs / PCs
```''')
    st.caption('Logical architecture from the review document. Exact topology, interface IDs, IP plan, VLAN assignments and routing statements must be aligned to the final Packet Tracer file.')
    st.markdown('### Implementation sequence')
    steps=[('1 · Address plan','Generate VLSM allocations and reserve gateways/infrastructure IPs.'),('2 · Layer 2','Create VLANs, assign access ports, configure 802.1Q trunks.'),('3 · Inter-VLAN routing','Configure router-on-a-stick subinterfaces using the plan gateways.'),('4 · DHCP','Create one pool per VLAN and exclude gateway/static addresses.'),('5 · Dynamic routing','Configure OSPF; use RIP only as a comparison if required by the review.'),('6 · NAT & upstream','Configure NAT overload on R1 and a route toward the simulated ISP.'),('7 · Verification','Run DHCP, same-VLAN ping, inter-VLAN ping, traceroute and routing/NAT show commands.')]
    for title,desc in steps: st.markdown(f'**{title}** — {desc}')
    st.markdown('### Packet Tracer CLI verification commands')
    st.code('show ip interface brief\nshow vlan brief\nshow interfaces trunk\nshow ip route\nshow ip ospf neighbor\nshow ip nat translations\nshow ip dhcp binding\nping <destination-ip>\ntraceroute <destination-ip>',language='text')
    st.info('The team’s documented working topology may use a smaller three-VLAN setup. This page follows the broader five-department architecture in the review document; update it to reflect the final .pkt file before presenting.')

elif page=='Performance Lab':
    st.markdown('<div class="section">Network performance lab</div>',unsafe_allow_html=True)
    st.write('Run controlled experiments on queue management and packet size. Keep all non-target parameters constant when comparing scenarios.')
    with st.expander('Model assumptions',expanded=False):
        st.markdown('- Packet arrivals are generated from an exponential inter-arrival distribution (Poisson traffic model).\n- FIFO queue with configurable packet limit.\n- Service time is packet bits divided by configured link bandwidth, so packet size affects link occupancy.\n- DropTail drops at a full queue; RED uses an exponentially weighted moving average and probabilistic early drop between thresholds.\n- This is an educational Python model, not NS2, NAM, Packet Tracer, or physical network measurement.')
    tab1,tab2=st.tabs(['Experiment A · DropTail vs RED','Experiment B · Packet size'])
    with tab1:
        c1,c2,c3=st.columns(3)
        with c1: duration=st.slider('Simulation duration (s)',5,60,20,key='qd')
        with c2: load=st.slider('Offered load (packets/s)',100,2500,800,50,key='ql')
        with c3: bandwidth=st.slider('Link bandwidth (Mbps)',1,100,5,key='qb')
        c4,c5,c6=st.columns(3)
        with c4: qlim=st.slider('Queue limit (packets)',10,200,50,key='qq')
        with c5: psize=st.select_slider('Packet size (bytes)',options=[128,256,512,750,1000,1200,1500],value=1000,key='qp')
        with c6: seed=st.number_input('Random seed',min_value=0,max_value=999999,value=7,key='qs')
        r1,r2=st.columns(2)
        with r1: red_min=st.slider('RED minimum threshold',0,max(1,qlim-2),10,key='rmin')
        with r2: red_max=st.slider('RED maximum threshold',2,qlim,30,key='rmax')
        if red_min>=red_max: st.warning('Set RED minimum threshold lower than maximum threshold.')
        if st.button('▶ Run queue comparison',type='primary',key='runqueue'):
            try:
                st.session_state.queue_results=[simulate_queue('DropTail',duration,load,bandwidth,qlim,psize,int(seed)),simulate_queue('RED',duration,load,bandwidth,qlim,psize,int(seed),red_min,red_max)]
            except Exception as e: st.error(str(e))
        if 'queue_results' in st.session_state:
            res=st.session_state.queue_results; rdf=pd.DataFrame([{k:v for k,v in x.items() if k not in ('queue_samples','assumptions')} for x in res])
            st.dataframe(rdf[['algorithm','packets_sent','packets_received','packets_lost','packet_loss_pct','delivery_ratio_pct','throughput_mbps','avg_delay_ms','avg_queue_packets']],use_container_width=True,hide_index=True)
            fig,axs=plt.subplots(1,3,figsize=(12,3.3))
            for ax,metric,title in zip(axs,['packet_loss_pct','throughput_mbps','avg_delay_ms'],['Packet loss (%)','Throughput (Mbps)','Average queue delay (ms)']):
                ax.bar(rdf['algorithm'],rdf[metric]); ax.set_title(title); ax.grid(axis='y',alpha=.25)
            st.pyplot(fig); plt.close(fig)
            st.download_button('Download queue comparison CSV',rdf.to_csv(index=False).encode(),file_name='droptail_vs_red.csv',mime='text/csv')
    with tab2:
        c1,c2,c3=st.columns(3)
        with c1: sd=st.slider('Duration (s)',5,60,20,key='sd')
        with c2: sl=st.slider('Offered load (packets/s)',100,2500,800,50,key='sl')
        with c3: sb=st.slider('Link bandwidth (Mbps)',1,100,5,key='sb')
        c4,c5,c6=st.columns(3)
        with c4: sq=st.slider('Queue limit (packets)',10,200,50,key='sq')
        with c5: ss=st.number_input('Fixed random seed',min_value=0,max_value=999999,value=7,key='ss')
        with c6: alg=st.selectbox('Queue algorithm',['DropTail','RED'],key='sa')
        if st.button('▶ Run packet-size sweep',type='primary',key='runsize'):
            try:
                results=[]
                for size in [128,256,512,750,1000,1200,1500]:
                    results.append(simulate_queue(alg,sd,sl,sb,sq,size,int(ss),min(10,sq-2),min(30,sq)))
                st.session_state.size_results=results
            except Exception as e: st.error(str(e))
        if 'size_results' in st.session_state:
            sdf=pd.DataFrame([{k:v for k,v in x.items() if k not in ('queue_samples','assumptions')} for x in st.session_state.size_results])
            st.dataframe(sdf[['packet_size_bytes','packets_sent','packets_received','packets_lost','packet_loss_pct','throughput_mbps','avg_delay_ms']],use_container_width=True,hide_index=True)
            fig,axs=plt.subplots(1,3,figsize=(12,3.3))
            for ax,metric,title in zip(axs,['throughput_mbps','avg_delay_ms','packet_loss_pct'],['Throughput (Mbps)','Average queue delay (ms)','Packet loss (%)']):
                ax.plot(sdf['packet_size_bytes'],sdf[metric],marker='o'); ax.set_xlabel('Packet size (bytes)'); ax.set_title(title); ax.grid(alpha=.25)
            st.pyplot(fig); plt.close(fig)
            st.download_button('Download packet-size results CSV',sdf.to_csv(index=False).encode(),file_name='packet_size_experiment.csv',mime='text/csv')
    st.caption('Interpretation: larger packets increase service time per packet at fixed link bandwidth. Results vary with load, queue limit, algorithm and seed. Report the exact settings and describe these as model outputs.')

elif page=='CLI & External Tools':
    st.markdown('<div class="section">Command line, NS2 & Wireshark integrations</div>',unsafe_allow_html=True)
    st.write('Run the planner from a terminal, analyze NS2 trace files, or summarize Wireshark captures through TShark.')
    c1,c2,c3=st.columns(3)
    with c1: st.metric('NS2', 'Available' if shutil.which('ns') else 'Install separately')
    with c2: st.metric('TShark', 'Available' if shutil.which('tshark') else 'Install Wireshark')
    with c3: st.metric('pytest', 'Run from terminal')
    st.markdown('### CLI examples')
    st.code('python campusnet_cli.py plan --base 192.168.0.0/23 --department CSE=120 --department ECE=120 --format csv --output plan.csv\npython campusnet_cli.py simulate --algorithm RED --seed 7 --output red.json\npython campusnet_cli.py analyze-ns2 ns2/results/red.tr --duration 10 --output red_trace.json\npython campusnet_cli.py analyze-pcap captures/campus.pcapng --filter "dhcp || dns" --output capture.json',language='powershell')
    st.markdown('### NS2 experiment')
    st.write('The Tcl scenario compares DropTail and RED at a bottleneck. NS2 writes trace and NAM files when you run it.')
    st.code('New-Item -ItemType Directory -Force ns2/results | Out-Null\nns ns2/campusnet.tcl DropTail ns2/results/droptail\nNew-Item -ItemType Directory -Force ns2/results | Out-Null\nns ns2/campusnet.tcl RED ns2/results/red\nnam ns2/results/red.nam',language='powershell')
    st.markdown('### Wireshark')
    st.write('Capture traffic in Wireshark and save a pcapng file. The CLI can summarize its packets, protocols and source addresses. See docs/WIRESHARK.md for filters and setup.')
    st.info('NS2 and Wireshark/TShark are external applications. A tool shown as unavailable has not been run on this machine. Keep outputs labeled with their source and settings.')

elif page=='Testing & Results':
    st.markdown('<div class="section">Verification matrix & results log</div>',unsafe_allow_html=True)
    tests=[('DHCP lease per department','Packet Tracer + optional Wireshark','Each host gets an address in its own subnet; DORA exchange visible.'),('Same-VLAN connectivity','ping','Replies received; expected local reachability.'),('Inter-department connectivity','ping + traceroute','Replies received; path follows configured routers.'),('Routing exchange','show ip route / show ip ospf neighbor / Wireshark','Required routes present; OSPF neighbours form when configured.'),('NAT access','ping + show ip nat translations','Internal hosts reach simulated ISP/server; translations appear.'),('Plan correctness','Python VLSM validator + pytest','No overlaps/out-of-range subnets; enough usable addresses.'),('Address utilization','Planner output / CSV','Compare fixed /24 allocation with VLSM.'),('NS2 traffic delivery','NS2 trace + campusnet_cli.py','Count sent/received packets; compute delivery ratio and loss.'),('Throughput and delay','NS2 trace + campusnet_cli.py','Calculate delivered bits/time and average trace delay.'),('Traffic load / queue behaviour','NS2 + NAM or Python Performance Lab','Compare multiple loads; visualize packet drops and metrics.'),('Routing behaviour / failure recovery','NS2 trace; Packet Tracer separately','Observe supported routing behaviour; verify Cisco routing independently.')]
    df=pd.DataFrame(tests,columns=['Test','Tool','Expected result']); st.dataframe(df,use_container_width=True,hide_index=True)
    st.markdown('### Record actual evidence')
    st.caption('Use this log to capture what you personally observed. Do not mark expected results as passed until tested.')
    if 'testlog' not in st.session_state: st.session_state.testlog=pd.DataFrame([{'Test':t[0],'Status':'Not tested','Evidence / notes':''} for t in tests])
    edited=st.data_editor(st.session_state.testlog,use_container_width=True,hide_index=True,key='testlog_editor',column_config={'Status':st.column_config.SelectboxColumn(options=['Not tested','Passed','Failed','Not applicable'])},num_rows='dynamic')
    st.session_state.testlog=edited
    st.download_button('Export verification log (CSV)',edited.to_csv(index=False).encode(),file_name='verification_log.csv',mime='text/csv')
    st.markdown('### Core metric definitions')
    st.latex(r'\text{Packet Delivery Ratio (\%)}=\frac{\text{Packets received}}{\text{Packets sent}}\times100')
    st.latex(r'\text{Packet Loss}=\text{Packets sent}-\text{Packets received}')
    st.latex(r'\text{Throughput} = \frac{\text{Received bits}}{\text{Observation time}}')
    st.latex(r'\text{Average end-to-end delay}=\frac{\sum \text{packet delays}}{\text{Packets received}}')

elif page=='Project Documentation':
    st.markdown('<div class="section">Project documentation & presentation notes</div>',unsafe_allow_html=True)
    st.markdown('### Final project title')
    st.info('VLSM-Based Subnet Planner and Configuration Generator with Simulated Campus Network Implementation')
    st.markdown('### Abstract')
    st.write('Small institutions often use fixed-size subnets regardless of actual host demand, wasting addresses and increasing the risk of manual addressing errors. This project combines a Python VLSM planner and validator, Cisco IOS configuration generation, a simulated campus topology, and network performance evaluation. The planner sorts department requirements, allocates appropriately sized private IPv4 subnets, validates capacity and overlap, and generates router/DHCP/switch configuration templates. Cisco Packet Tracer is used for VLANs, inter-VLAN routing, DHCP, NAT and dynamic routing verification. NS2 is the target environment for TCP and UDP/CBR traffic experiments; the included Python Performance Lab is a separate educational queueing model used for DropTail-vs-RED and packet-size comparisons.')
    st.markdown('### Problem statement & objectives')
    st.write('Manual fixed-size subnetting wastes address space, creates opportunities for overlapping or invalid ranges, and is difficult to scale. Objectives: (1) allocate subnets based on actual host requirements; (2) validate overlap, ranges and capacity; (3) generate router/DHCP configurations; (4) implement VLANs, inter-VLAN routing, DHCP, NAT and RIP/OSPF in a simulated campus; (5) compare address utilization for fixed /24 versus VLSM; (6) evaluate packet delivery, loss, throughput, delay, routing behaviour, queue algorithms and packet size.')
    st.markdown('### Tools and implementation status')
    tools=[('Python + ipaddress','Planner sizing, private-range and capacity validation are implemented'),('Streamlit','Interactive application interface is implemented'),('CSV / JSON','Exports are available from the app and CLI'),('argparse','Command-line interface is implemented in campusnet_cli.py'),('pytest','Automated test files are included; run them with python -m pytest -v'),('NS2 Tcl','DropTail/RED scenario and trace analyzer are included; NS2 must be installed to run'),('Wireshark / TShark','Capture-analysis CLI is included; Wireshark/TShark must be installed and a capture supplied'),('Cisco Packet Tracer','External topology and connectivity validation; run separately'),('NAM','Optional viewer for NS2 animation files'),('Git / VS Code','Development and version-control tools')]
    st.dataframe(pd.DataFrame(tools,columns=['Tool','Status in this project']),use_container_width=True,hide_index=True)
    st.markdown('### Important scope and integrity notes')
    st.warning('The sample values in the report are illustrative and must be confirmed against the final demonstration. The sample plan has 5 departments and 405 hosts. The app does not execute Cisco Packet Tracer or native NS2, does not capture Wireshark packets, and does not automatically import IOS configs into NS2. Keep actual implementation evidence separate from expected outcomes.')
    st.markdown('### References from the supplied review document')
    refs=[
    '[1] “Efficient IPv4 address allocation using VLSM and CIDR: A university network case study with simulation validation,” ResearchGate, 2026. https://www.researchgate.net/publication/403730162',
    '[2] N. Dhandala, “How to use VLSM for efficient address allocation,” OneUptime Blog, Mar. 20, 2026. https://oneuptime.com/blog/post/2026-03-20-use-vlsm-efficient-address-allocation/view',
    '[3] Fitria, M. A. I. Mashuri, and Rosita, “Campus network design and construction using Cisco Packet Tracer simulation,” J. Appl. Inform. Res., vol. 1, no. 1, pp. 45–56, Jul. 2025, doi:10.26740/jair.v1i1.44676.',
    '[4] V. Fuller and T. Li, “Classless Inter-domain Routing (CIDR): The Internet address assignment and aggregation plan,” IETF RFC 4632, Aug. 2006.',
    '[5] Y. Rekhter et al., “Address allocation for private internets,” IETF RFC 1918, Feb. 1996.',
    '[6] R. Droms, “Dynamic Host Configuration Protocol,” IETF RFC 2131, Mar. 1997.',
    '[7] P. Srisuresh and K. Egevang, “Traditional IP Network Address Translator (Traditional NAT),” IETF RFC 3022, Jan. 2001.',
    '[8] Y. E. Yousif and O. A. O. Elnageeb, “Performance evaluation and comparison of RIP, EIGRP and OSPF routing protocols,” Eur. J. Appl. Sci., Eng. Technol., vol. 3, no. 3, pp. 303–308, 2025, doi:10.59324/ejaset.2025.3(3).21.',
    '[9] J. Moy, “OSPF version 2,” IETF RFC 2328, Apr. 1998.'
    ]
    for ref in refs: st.markdown('- '+ref)
    st.markdown('### Team')
    st.write('Arihant Singi (24BCT0305) · Shrey Thorat (24BCB0067)')

st.divider()
st.caption('CampusNet Studio · Computer Networks project · Generated configurations and simulations are educational outputs; verify against the final topology and course requirements.')
