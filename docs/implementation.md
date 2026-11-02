# Implementation plan

## Safety and status
Stage 1 prototype only. Synthetic paper broker and API transport are implemented; no prices, news feeds, Telegram, EC2 deployment, database, CI, or live orders are operational.
No real-order adapter exists. Never share keys, tokens, Telegram chat IDs, private holdings or AWS credentials in this public repository. Use noncommitted restricted server environment or AWS SSM.
The AI model may classify untrusted text only; its output cannot submit orders.

## Budget
Target INR 1320/month: EC2 670, data 0, AI 500, miscellaneous 150. Real EC2 instance + storage + public IPv4 + taxes may exceed this and must be estimated before launch. AWS Budgets are alarms, not spending hard caps.

## EC2 planned configuration
Ubuntu 24.04 on t3.small with 20 GiB gp3 EBS in ap-south-1. Prefer Systems Manager to open SSH, or restrict SSH by source IP. Do not expose dashboard ports. Provision only after validation and budget alarms. Use persistent data, service supervision, protected secrets and encrypted backups before unattended use.

## Development milestones
1. [x] Public repo, branch, small synthetic paper broker, initial risk tests, DeepSeek/GLM client.
2. [ ] CI GitHub Actions workflow, secure secret management and dependency scanning.
3. [ ] Read-only broker feed integration; historical market data and database.
4. [ ] Permitted exchange/issuer news feeds; timestamps, source attribution, issuer matching.
5. [ ] Realistic market fills, charges, slippage and corporate actions; unbiased backtesting.
6. [ ] Telegram alerts, private dashboard, deployment hardening and monitoring.
7. [ ] EC2 deployment and at least 90 forward paper-trading sessions.
8. [ ] Evaluate separately authorized live trading with sandbox/shadow mode and compliance, only after paper evidence.

## Usage
Install Python 3.11+, run `pip install -e ".[dev]"`, `pytest -q` and `python -m trading.cli`.
Provider access requires general-purpose API keys; coding subscriptions alone may not qualify. Don't commit keys.
