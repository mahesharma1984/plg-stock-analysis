#!/usr/bin/env python3
"""
RALPH Genesis Analyzer
Traces token origin to identify dev/team/insider wallets.

Analyzes:
1. Token deployer (mint authority)
2. First recipients after mint
3. Wallet funding sources
4. Risk scoring based on genesis proximity
"""

import json
import requests
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table

console = Console()

# RALPH token address
RALPH_TOKEN = "CxWPdDBqxVo3fnTMRTvNuSrd4gkp78udSrFvkVDBAGS"

RPC_URLS = [
    "https://mainnet.helius-rpc.com/?api-key=e359478f-68a9-4663-9e11-681093537853",
    "https://api.mainnet-beta.solana.com",
]


@dataclass
class WalletGenesis:
    """Genesis information for a wallet."""
    address: str
    label: str
    first_received_at: Optional[str]
    first_amount: int
    funded_by: Optional[str]
    is_original_recipient: bool
    risk_score: int  # 0-100, higher = more likely insider
    risk_factors: List[str]


class GenesisAnalyzer:
    """Analyzes token genesis to identify insider wallets."""

    def __init__(self, token_mint: str = RALPH_TOKEN):
        self.token_mint = token_mint
        self.session = requests.Session()
        self.rpc_index = 0

    def _rpc_call(self, method: str, params: List[Any]) -> Optional[Dict]:
        """Make RPC call with retry."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }

        for attempt in range(3):
            try:
                url = RPC_URLS[self.rpc_index % len(RPC_URLS)]
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    console.print(f"[yellow]RPC error: {result['error']}[/yellow]")
                    self.rpc_index += 1
                    time.sleep(1)
                    continue

                return result.get("result")

            except Exception as e:
                console.print(f"[yellow]RPC failed (attempt {attempt + 1}): {e}[/yellow]")
                self.rpc_index += 1
                time.sleep(2)

        return None

    def get_token_supply(self) -> Optional[Dict]:
        """Get token supply and mint info."""
        result = self._rpc_call("getTokenSupply", [self.token_mint])
        return result

    def get_token_largest_accounts(self, limit: int = 20) -> Optional[List[Dict]]:
        """Get largest token holders."""
        result = self._rpc_call("getTokenLargestAccounts", [self.token_mint])
        if result and "value" in result:
            return result["value"][:limit]
        return None

    def get_account_info(self, address: str) -> Optional[Dict]:
        """Get account info including owner."""
        result = self._rpc_call("getAccountInfo", [
            address,
            {"encoding": "jsonParsed"}
        ])
        if result and "value" in result:
            return result["value"]
        return None

    def get_signatures(self, address: str, limit: int = 1000, before: str = None) -> Optional[List[Dict]]:
        """Get transaction signatures for address."""
        params = {"limit": limit}
        if before:
            params["before"] = before
        result = self._rpc_call("getSignaturesForAddress", [address, params])
        return result

    def get_transaction(self, signature: str) -> Optional[Dict]:
        """Get parsed transaction."""
        result = self._rpc_call("getTransaction", [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        ])
        return result

    def find_mint_authority(self) -> Optional[str]:
        """Find the mint authority (deployer) of the token."""
        console.print("[cyan]Finding mint authority...[/cyan]")

        # Get mint account info
        result = self._rpc_call("getAccountInfo", [
            self.token_mint,
            {"encoding": "jsonParsed"}
        ])

        if not result or not result.get("value"):
            console.print("[red]Could not get token mint info[/red]")
            return None

        try:
            parsed = result["value"]["data"]["parsed"]["info"]
            mint_authority = parsed.get("mintAuthority")
            freeze_authority = parsed.get("freezeAuthority")

            console.print(f"  Mint Authority: {mint_authority or 'DISABLED'}")
            console.print(f"  Freeze Authority: {freeze_authority or 'DISABLED'}")

            return mint_authority
        except (KeyError, TypeError) as e:
            console.print(f"[red]Error parsing mint info: {e}[/red]")
            return None

    def find_first_transactions(self, limit: int = 100) -> List[Dict]:
        """Find earliest transactions for the token mint."""
        console.print(f"[cyan]Finding earliest token transactions...[/cyan]")

        all_sigs = []
        before = None

        # Paginate to get oldest transactions
        while len(all_sigs) < limit:
            sigs = self.get_signatures(self.token_mint, limit=1000, before=before)
            if not sigs:
                break

            all_sigs.extend(sigs)
            before = sigs[-1]["signature"]

            console.print(f"  Found {len(all_sigs)} signatures...")

            # Rate limit
            time.sleep(0.5)

            # If we got less than 1000, we've reached the beginning
            if len(sigs) < 1000:
                break

        # Sort by block time (oldest first)
        all_sigs.sort(key=lambda x: x.get("blockTime", 0))

        console.print(f"  Total signatures: {len(all_sigs)}")
        if all_sigs:
            oldest = datetime.fromtimestamp(all_sigs[0].get("blockTime", 0), tz=timezone.utc)
            console.print(f"  Oldest transaction: {oldest.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        return all_sigs[:50]  # Return first 50 for analysis

    def analyze_early_recipients(self, signatures: List[Dict]) -> Dict[str, Dict]:
        """Analyze early transactions to find first recipients."""
        console.print(f"\n[cyan]Analyzing {len(signatures)} early transactions...[/cyan]")

        recipients = {}

        for i, sig_info in enumerate(signatures[:30]):  # Analyze first 30
            sig = sig_info["signature"]
            block_time = sig_info.get("blockTime", 0)

            console.print(f"  [{i+1}/30] Analyzing {sig[:16]}...")

            tx = self.get_transaction(sig)
            if not tx:
                continue

            # Parse transaction for token transfers
            try:
                meta = tx.get("meta", {})
                post_balances = meta.get("postTokenBalances", [])
                pre_balances = meta.get("preTokenBalances", [])

                # Find accounts that received tokens
                for post in post_balances:
                    if post.get("mint") != self.token_mint:
                        continue

                    owner = post.get("owner")
                    if not owner:
                        continue

                    amount = int(post.get("uiTokenAmount", {}).get("amount", 0))

                    # Check if this is a new recipient
                    pre_amount = 0
                    for pre in pre_balances:
                        if pre.get("owner") == owner and pre.get("mint") == self.token_mint:
                            pre_amount = int(pre.get("uiTokenAmount", {}).get("amount", 0))
                            break

                    received = amount - pre_amount
                    if received > 0 and owner not in recipients:
                        recipients[owner] = {
                            "first_tx": sig,
                            "first_time": block_time,
                            "first_amount": received,
                            "tx_index": i
                        }

            except Exception as e:
                console.print(f"    [yellow]Parse error: {e}[/yellow]")
                continue

            time.sleep(0.3)  # Rate limit

        return recipients

    def analyze_wallet_funding(self, wallet: str) -> Optional[str]:
        """Find where a wallet's SOL came from."""
        sigs = self.get_signatures(wallet, limit=100)
        if not sigs:
            return None

        # Get oldest transaction
        sigs.sort(key=lambda x: x.get("blockTime", 0))

        for sig_info in sigs[:5]:
            tx = self.get_transaction(sig_info["signature"])
            if not tx:
                continue

            try:
                # Look for SOL transfer into this wallet
                message = tx.get("transaction", {}).get("message", {})
                instructions = message.get("instructions", [])

                for inst in instructions:
                    if inst.get("program") == "system":
                        parsed = inst.get("parsed", {})
                        if parsed.get("type") == "transfer":
                            info = parsed.get("info", {})
                            if info.get("destination") == wallet:
                                return info.get("source")

            except Exception:
                continue

            time.sleep(0.2)

        return None

    def calculate_risk_score(self, wallet: str, genesis_data: Dict,
                             mint_authority: str, early_recipients: Dict) -> WalletGenesis:
        """Calculate risk score for a wallet based on genesis proximity."""

        risk_score = 0
        risk_factors = []

        # Check if wallet is mint authority
        if wallet == mint_authority:
            risk_score += 50
            risk_factors.append("IS MINT AUTHORITY (deployer)")

        # Check if wallet was early recipient
        if wallet in early_recipients:
            recipient_info = early_recipients[wallet]
            tx_index = recipient_info["tx_index"]

            if tx_index < 5:
                risk_score += 40
                risk_factors.append(f"Top 5 earliest recipient (tx #{tx_index + 1})")
            elif tx_index < 10:
                risk_score += 25
                risk_factors.append(f"Top 10 earliest recipient (tx #{tx_index + 1})")
            elif tx_index < 20:
                risk_score += 15
                risk_factors.append(f"Top 20 earliest recipient (tx #{tx_index + 1})")

        # Check funding source
        funding_source = self.analyze_wallet_funding(wallet)
        if funding_source:
            if funding_source == mint_authority:
                risk_score += 30
                risk_factors.append("Funded by mint authority")
            elif funding_source in early_recipients:
                risk_score += 20
                risk_factors.append("Funded by early recipient")

        # Large holder bonus
        if genesis_data.get("pct_supply", 0) > 5:
            risk_score += 10
            risk_factors.append(f"Large holder ({genesis_data.get('pct_supply', 0):.1f}% supply)")

        return WalletGenesis(
            address=wallet,
            label=genesis_data.get("label", "unknown"),
            first_received_at=early_recipients.get(wallet, {}).get("first_time"),
            first_amount=early_recipients.get(wallet, {}).get("first_amount", 0),
            funded_by=funding_source,
            is_original_recipient=wallet in early_recipients,
            risk_score=min(risk_score, 100),
            risk_factors=risk_factors
        )

    def run_analysis(self, tracked_wallets: Dict[str, str] = None) -> List[WalletGenesis]:
        """Run full genesis analysis."""

        console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]              GENESIS ANALYZER - INSIDER DETECTION          [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

        console.print(f"Token: {self.token_mint}\n")

        # Step 1: Find mint authority
        mint_authority = self.find_mint_authority()

        # Step 2: Get token supply info
        supply_info = self.get_token_supply()
        if supply_info:
            total_supply = int(supply_info["value"]["amount"])
            decimals = supply_info["value"]["decimals"]
            console.print(f"\nTotal Supply: {total_supply / 10**decimals:,.0f}")

        # Step 3: Find earliest transactions
        early_sigs = self.find_first_transactions()

        # Step 4: Analyze early recipients
        early_recipients = self.analyze_early_recipients(early_sigs)

        console.print(f"\n[green]Found {len(early_recipients)} early recipients[/green]")

        # Step 5: Analyze tracked wallets
        results = []

        if tracked_wallets:
            console.print(f"\n[cyan]Analyzing {len(tracked_wallets)} tracked wallets...[/cyan]\n")

            for label, wallet in tracked_wallets.items():
                console.print(f"  Analyzing {label}...")

                genesis_data = {
                    "label": label,
                    "pct_supply": 0  # Could calculate from current balance
                }

                result = self.calculate_risk_score(
                    wallet, genesis_data, mint_authority, early_recipients
                )
                results.append(result)

                time.sleep(0.2)

        # Also analyze top early recipients not in tracked list
        for wallet, info in list(early_recipients.items())[:10]:
            if tracked_wallets and wallet in tracked_wallets.values():
                continue

            genesis_data = {
                "label": f"early_recipient_{info['tx_index']}",
                "pct_supply": 0
            }

            result = self.calculate_risk_score(
                wallet, genesis_data, mint_authority, early_recipients
            )
            results.append(result)

        # Sort by risk score
        results.sort(key=lambda x: x.risk_score, reverse=True)

        return results

    def print_results(self, results: List[WalletGenesis]):
        """Print analysis results."""

        console.print("\n[bold]═══════════════════════════════════════════════════════════[/bold]")
        console.print("[bold]                    RISK ASSESSMENT RESULTS                 [/bold]")
        console.print("[bold]═══════════════════════════════════════════════════════════[/bold]\n")

        table = Table(title="Wallet Risk Scores")
        table.add_column("Wallet", style="cyan", max_width=12)
        table.add_column("Address", max_width=16)
        table.add_column("Risk", justify="center")
        table.add_column("Factors", max_width=40)

        for r in results:
            # Risk color
            if r.risk_score >= 70:
                risk_str = f"[red bold]{r.risk_score}[/red bold]"
            elif r.risk_score >= 40:
                risk_str = f"[yellow]{r.risk_score}[/yellow]"
            else:
                risk_str = f"[green]{r.risk_score}[/green]"

            factors = ", ".join(r.risk_factors) if r.risk_factors else "No risk factors"

            table.add_row(
                r.label,
                r.address[:8] + "..." + r.address[-4:],
                risk_str,
                factors
            )

        console.print(table)

        # Summary
        high_risk = [r for r in results if r.risk_score >= 70]
        if high_risk:
            console.print(f"\n[red bold]⚠ HIGH RISK WALLETS ({len(high_risk)}):[/red bold]")
            for r in high_risk:
                console.print(f"  • {r.label}: {r.address}")
                for factor in r.risk_factors:
                    console.print(f"    - {factor}")


def main():
    """Run genesis analysis for RALPH token."""

    # Tracked wallets from ralph_tracker
    tracked_wallets = {
        "whale_1": "B93svZrj7Rd7U4x3kzdVw72WeVDEu1ZqGJ44RqRM6mq5",
        "whale_2": "4h2LVG9N7MberHdFogR9VsSoTpVcvChQCpmRPCPzw4QL",
        "whale_3": "D6CZvbnsjffowaS4zagotHfdmZthxNBVqKwzp9C3tZYS",
        "whale_4": "2mvtNnTP2CBRz24q1BzmDX9cv2bQBsY8E77D32qkYKCm",
        "whale_5": "GHzMXqRg9rY9PkqJZB3go87z9Tq7iPovTJnbLddYqBmx",
        "whale_6": "9qMEvPibix8AsdwXsNLJQuNTfTEj1g5kz8LnzNzqYtai",
        "whale_7": "54ex3KwZ34CJSQyonBnvA8bkNpMhXF5qRCAW3y7JYTJh",
        "whale_8": "DgtqzuB3p7bCXTGxtYUbvUApEKco2qgevpMB1b6sKmov",
        "whale_9": "CduMPoQNsBvZ1g9QneAgFMobbyUceUykWwmixVG4yukT",
        "whale_10": "A12G3UBUfGZbWpc5QJQb3P9gonfBSqoaeU4TLaRQrDQV",
    }

    analyzer = GenesisAnalyzer(RALPH_TOKEN)
    results = analyzer.run_analysis(tracked_wallets)
    analyzer.print_results(results)


if __name__ == "__main__":
    main()
