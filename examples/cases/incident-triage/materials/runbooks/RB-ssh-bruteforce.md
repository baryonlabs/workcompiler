# RB: SSH brute force
1. Confirm failed-login count in auth.log for the source IP.
2. Block the source IP at the edge firewall (temporary, 24h).
3. Verify no successful login from that IP; if any, escalate to on-call.
