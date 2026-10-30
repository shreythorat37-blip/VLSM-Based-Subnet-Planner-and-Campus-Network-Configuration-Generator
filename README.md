# CampusNet Studio

**Full project title:** VLSM-Based Subnet Planner and Configuration Generator with Simulated Campus Network Implementation

A polished, integrated Computer Networks project workspace based on the supplied Project Review-1 document. It includes:

- Interactive VLSM planner for private IPv4 networks, sorted allocation, subnet validation and capacity checks.
- Address-utilization comparison for fixed /24 versus VLSM.
- CSV and JSON exports from the app and command-line interface.
- Cisco IOS router subinterface, DHCP pool and switch VLAN configuration templates.
- Campus topology and Packet Tracer implementation checklist for VLANs, inter-VLAN routing, DHCP, NAT and OSPF/RIP.
- Performance Lab experiments: DropTail vs RED and packet-size sweeps, with throughput, packet loss, delivery ratio, average queue delay and CSV downloads.
- Verification matrix, test evidence log, metric definitions, tools and references from the supplied review document.
- Runnable NS2 DropTail/RED scenario, NS2 trace analyzer, optional Wireshark/TShark capture analyzer, and setup guides.

## Run on Windows in VS Code

1. Extract the ZIP completely.
2. In VS Code, select **File → Open Folder** and open the folder containing `app.py` and `requirements.txt`.
3. Open **Terminal → New Terminal** and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -v
streamlit run app.py
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again. If `requirements.txt` is not found, you opened the wrong folder: navigate to the folder that contains `app.py` and `requirements.txt`.

## Command-line tools and external integrations

The project includes campusnet_cli.py using Python argparse for VLSM plans, queue simulations, NS2 trace summaries, and optional TShark capture summaries. CSV and JSON output are supported. argparse is part of the Python standard library.

    python campusnet_cli.py plan --base 192.168.0.0/23 --department CSE=120 --department ECE=120 --format csv --output plan.csv
    python campusnet_cli.py simulate --algorithm RED --seed 7 --output red.json
    python campusnet_cli.py analyze-ns2 ns2/results/red.tr --duration 10 --output red_trace.json
    python campusnet_cli.py analyze-pcap captures/campus.pcapng --filter "dhcp || dns" --output capture.json

Run the NS2 comparison with ns ns2/campusnet.tcl DropTail ns2/results/droptail and the corresponding RED command. NS2/NAM and Wireshark/TShark must be installed separately. See ns2/README.md and docs/WIRESHARK.md.

## Project team

- Arihant Singi — 24BCT0305
- Shrey Thorat — 24BCB0067

## Important implementation boundary

The Streamlit app runs a Python educational queue simulation. It does **not** execute NS2, NAM, Wireshark or Cisco Packet Tracer, and it does not automatically import Cisco IOS configuration into NS2. The NS2 Tcl file is an executable scenario, and the CLI can analyze its classic trace output. NS2/NAM and Wireshark/TShark remain separate installations. Use actual traces and packet captures for claims about those tools. The sample host counts are illustrative and should be replaced with the final scenario where required.

## Recommended GitHub setup

Create an empty GitHub repository, then from this folder:

```powershell
git init
git add .
git commit -m "Build CampusNet Studio integrated computer networks project"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/CampusNet-Studio.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username.

## Presentation materials

See docs/PRESENTATION_GUIDE.md for a timed demo plan, sample explanation, viva questions, and evidence checklist. See docs/REPORT_TEMPLATE.md for a structured report template. Both distinguish implemented outputs from external Packet Tracer/NS2 evidence.

