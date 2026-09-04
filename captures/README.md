# Local raw captures

Store field-session directories here. Git ignores their contents because raw JSON
and PCAP files can contain local addresses, device IDs, serial numbers and names.
Only copy reviewed, sanitized JSON into `tests/fixtures/`.
