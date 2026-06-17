import re

# Patterns commonly found in network diagnostic logs pasted into email body
LOG_PATTERNS = [
    # Ping output
    r'\d+ bytes from .+: icmp_seq=\d+',           # Linux ping
    r'Reply from .+: bytes=\d+',                   # Windows ping
    r'Request timeout for icmp_seq',               # Mac/Linux timeout
    r'\d+ packets transmitted, \d+ received',      # Ping summary
    r'\d+% packet loss',                           # Packet loss line
    r'min/avg/max',                                # Ping RTT summary

    # Traceroute / MTR output
    r'^\s*\d+\s+[\w\.\-]+\s+\d+\.\d+ ms',        # traceroute hop line
    r'\* \* \*',                                   # traceroute timeout hop
    r'traceroute to',                              # traceroute header
    r'Tracing route to',                           # Windows tracert header
    r'Loss%\s+Snt',                                # MTR header

    # Interface / syslog style
    r'%\w+-\d+-\w+:',                             # Cisco syslog e.g. %LINK-3-UPDOWN
    r'Interface .+ (up|down)',                     # Interface state
    r'line protocol is (up|down)',                 # Cisco interface state
    r'(GigabitEthernet|FastEthernet|TenGig)\d+/\d+',  # Interface names

    # Timestamps in log format
    r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',  # ISO timestamp
    r'\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}',          # Syslog timestamp e.g. Jan  1 12:00:00

    # BGP / routing
    r'BGP state.*(Established|Idle|Active|OpenSent)',
    r'Neighbor .+ (Up|Down)',

    # General error/warning patterns in logs
    r'(ERROR|WARN|CRITICAL|ALERT|DOWN|FLAP)\s*:',
]

# Minimum number of pattern matches to consider the body as a log
MIN_MATCHES = 2


def is_log_content(text: str) -> bool:
    """
    Returns True if the email body appears to contain pasted log/diagnostic output.
    Uses regex pattern matching — no LLM call required.
    """
    if not text:
        return False

    match_count = 0
    for pattern in LOG_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            match_count += 1
            if match_count >= MIN_MATCHES:
                return True

    return False
