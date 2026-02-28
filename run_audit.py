#!/usr/bin/env python3
"""
Interactive Automaton Auditor - Run audits for self, peer, and receive peer reports
"""

import os
import sys
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich.markdown import Markdown
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from src.graph import AutomatonAuditor

# Initialize rich console
console = Console()
load_dotenv()


class AuditManager:
    """Manages different types of audits and report handling"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.audit_dir = self.base_dir / "audits"
        self.self_audit_dir = self.audit_dir / "report_onself_generated"
        self.peer_audit_dir = self.audit_dir / "report_onpeer_generated"
        self.received_dir = self.audit_dir / "report_bypeer_received"
        self.logs_dir = self.audit_dir / "langsmith_logs"
        
        # Create directories if they don't exist
        for dir_path in [self.self_audit_dir, self.peer_audit_dir, 
                         self.received_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def display_header(self, title: str):
        """Display a styled header"""
        console.print(Panel.fit(
            f"[bold cyan]{title}[/bold cyan]",
            border_style="bright_blue"
        ))
    
    def get_repo_info(self) -> Dict[str, str]:
        """Get repository information interactively"""
        console.print("\n[bold yellow]📦 Repository Information[/bold yellow]")
        
        repo_url = questionary.text(
            "Enter GitHub repository URL:",
            validate=lambda text: len(text) > 0 and ("github.com" in text or "git@github.com" in text)
        ).ask()
        
        # Auto-detect if it's a peer's repo or own repo
        is_peer = questionary.confirm(
            "Is this a peer's repository?",
            default=False
        ).ask()
        
        peer_name = None
        if is_peer:
            peer_name = questionary.text(
                "Enter peer's name (for report naming):",
                validate=lambda text: len(text) > 0
            ).ask()
        
        return {
            "url": repo_url,
            "is_peer": is_peer,
            "peer_name": peer_name
        }
    
    def get_pdf_path(self) -> Path:
        """Get PDF file path interactively"""
        console.print("\n[bold yellow]📄 PDF Report[/bold yellow]")
        
        # Show PDF files in current directory
        pdf_files = list(Path(".").glob("*.pdf"))
        if pdf_files:
            console.print("[dim]Found PDF files:[/dim]")
            for i, pdf in enumerate(pdf_files, 1):
                console.print(f"  {i}. {pdf.name}")
        
        pdf_path = questionary.path(
            "Enter path to PDF report:",
            validate=lambda path: Path(path).exists() and Path(path).suffix.lower() == '.pdf'
        ).ask()
        
        return Path(pdf_path)
    
    def select_audit_type(self) -> str:
        """Select the type of audit to perform"""
        console.print("\n[bold yellow]🔍 Select Audit Type[/bold yellow]")
        
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "1️⃣  Run audit on MY OWN repository",
                "2️⃣  Run audit on PEER'S repository",
                "3️⃣  View/Manage received peer reports",
                "4️⃣  Compare audits",
                "5️⃣  Exit"
            ]
        ).ask()
        
        return choice
    
    def run_self_audit(self, repo_url: str, pdf_path: Path):
        """Run audit on own repository"""
        console.print("\n[bold green]🚀 Running Self-Audit[/bold green]")
        
        timestamp = json.dumps({"current_time": datetime.now().strftime("%Y%m%d_%H%M%S")})
        thread_id = str(uuid.uuid4())
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("[cyan]Initializing auditor...", total=4)
            
            try:
                # Initialize auditor
                auditor = AutomatonAuditor()
                progress.update(task, advance=1, description="[cyan]Cloning repository...")
                
                # Run audit
                progress.update(task, description="[cyan]Running forensic analysis...")
                result = auditor.run(str(repo_url), str(pdf_path), thread_id=thread_id)
                progress.update(task, advance=1)
                
                # Generate report filename
                report_filename = f"self_audit_{timestamp}.md"
                report_path = self.self_audit_dir / report_filename
                
                # Save report with metadata
                self._save_audit_report(result, report_path, {
                    "type": "self",
                    "repo": repo_url,
                    "timestamp": timestamp,
                    "thread_id": thread_id
                })
                
                progress.update(task, advance=1, description="[green]Audit complete!")
                
                # Display summary
                self._display_audit_summary(result, report_path)
                
            except Exception as e:
                console.print(f"\n[bold red]❌ Audit failed: {str(e)}[/bold red]")
    
    def run_peer_audit(self, repo_url: str, pdf_path: Path, peer_name: str):
        """Run audit on peer's repository"""
        console.print(f"\n[bold yellow]👥 Running Peer Audit for {peer_name}[/bold yellow]")
        
        timestamp = json.dumps({"current_time": datetime.now().strftime("%Y%m%d_%H%M%S")})
        thread_id = str(uuid.uuid4())
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            task = progress.add_task("[cyan]Initializing auditor...", total=4)
            
            try:
                # Initialize auditor
                auditor = AutomatonAuditor()
                progress.update(task, advance=1, description="[cyan]Cloning peer repository...")
                
                # Run audit
                progress.update(task, description="[cyan]Analyzing peer code...")
                result = auditor.run(str(repo_url), str(pdf_path), thread_id=thread_id)
                progress.update(task, advance=1)
                
                # Generate report filename
                report_filename = f"peer_{peer_name}_audit_{timestamp}.md"
                report_path = self.peer_audit_dir / report_filename
                
                # Save report with metadata
                self._save_audit_report(result, report_path, {
                    "type": "peer",
                    "peer": peer_name,
                    "repo": repo_url,
                    "timestamp": timestamp,
                    "thread_id": thread_id
                })
                
                progress.update(task, advance=1, description="[green]Peer audit complete!")
                
                # Display summary
                self._display_audit_summary(result, report_path, is_peer=True)
                
            except Exception as e:
                console.print(f"\n[bold red]❌ Peer audit failed: {str(e)}[/bold red]")
    
    def receive_peer_report(self):
        """Receive and store a peer's audit report"""
        console.print("\n[bold magenta]📥 Receive Peer Report[/bold magenta]")
        
        # Get peer name
        peer_name = questionary.text(
            "Enter peer's name:",
            validate=lambda text: len(text) > 0
        ).ask()
        
        # Get report file
        report_path = questionary.path(
            "Enter path to received report file:",
            validate=lambda path: Path(path).exists()
        ).ask()
        
        report_path = Path(report_path)
        
        # Copy report to received directory
        timestamp = json.dumps({"current_time": datetime.now().strftime("%Y%m%d_%H%M%S")})
        dest_filename = f"from_{peer_name}_{timestamp}{report_path.suffix}"
        dest_path = self.received_dir / dest_filename
        
        shutil.copy2(report_path, dest_path)
        
        # Save metadata
        metadata = {
            "peer": peer_name,
            "received_at": timestamp,
            "original_filename": report_path.name,
            "file_size": report_path.stat().st_size
        }
        
        metadata_path = dest_path.with_suffix('.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        console.print(f"[green]✅ Report saved to: {dest_path}[/green]")
        
        # Ask if they want to view it
        if questionary.confirm("View the received report?").ask():
            self._display_received_report(dest_path)
    
    def view_received_reports(self):
        """View all received peer reports"""
        console.print("\n[bold magenta]📚 Received Reports[/bold magenta]")
        
        reports = list(self.received_dir.glob("*.md"))
        if not reports:
            console.print("[yellow]No received reports found.[/yellow]")
            return
        
        # Create table
        table = Table(title="Received Peer Reports")
        table.add_column("#", style="cyan")
        table.add_column("Peer", style="green")
        table.add_column("Date Received", style="yellow")
        table.add_column("File", style="white")
        table.add_column("Size", style="blue")
        
        for i, report in enumerate(sorted(reports, key=lambda x: x.stat().st_ctime, reverse=True), 1):
            # Try to extract peer name from filename
            parts = report.stem.split('_')
            peer = parts[1] if len(parts) > 1 else "Unknown"
            
            # Get creation time
            ctime = str(datetime.fromtimestamp(report.stat().st_ctime).strftime("%Y-%m-%d %H:%M"))
            
            table.add_row(
                str(i),
                peer,
                ctime,
                report.name[:30] + "..." if len(report.name) > 30 else report.name,
                f"{report.stat().st_size / 1024:.1f} KB"
            )
        
        console.print(table)
        
        # Ask if they want to view a specific report
        if reports:
            choice = questionary.select(
                "Select a report to view (or Cancel to exit):",
                choices=[report.name for report in reports] + ["Cancel"]
            ).ask()
            
            if choice != "Cancel":
                selected = next(r for r in reports if r.name == choice)
                self._display_received_report(selected)
    
    def compare_audits(self):
        """Compare self audit with received peer audit"""
        console.print("\n[bold blue]📊 Compare Audits[/bold blue]")
        
        # Get self audits
        self_audits = list(self.self_audit_dir.glob("*.md"))
        if not self_audits:
            console.print("[yellow]No self audits found. Run a self audit first.[/yellow]")
            return
        
        # Get received reports
        received = list(self.received_dir.glob("*.md"))
        if not received:
            console.print("[yellow]No received peer reports found.[/yellow]")
            return
        
        # Let user select which to compare
        self_choice = questionary.select(
            "Select your self-audit:",
            choices=[f"{i+1}. {a.name}" for i, a in enumerate(self_audits)]
        ).ask()
        
        peer_choice = questionary.select(
            "Select peer report to compare:",
            choices=[f"{i+1}. {r.name}" for i, r in enumerate(received)]
        ).ask()
        
        # Extract indices
        self_idx = int(self_choice.split('.')[0]) - 1
        peer_idx = int(peer_choice.split('.')[0]) - 1
        
        self_path = self_audits[self_idx]
        peer_path = received[peer_idx]
        
        # Display comparison
        self._display_comparison(self_path, peer_path)
    
    def _save_audit_report(self, result: Dict[str, Any], report_path: Path, metadata: Dict):
        """Save audit report with metadata"""
        # Save main report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(result.get('final_report', '# No report generated'))
        
        # Save metadata
        metadata_path = report_path.with_suffix('.json')
        metadata.update({
            "evidence_count": len(result.get('evidences', {})),
            "opinion_count": len(result.get('opinions', [])),
            "criteria_count": len(result.get('rubric_dimensions', []))
        })
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Save evidence summary
        evidence_path = self.logs_dir / f"evidence_{metadata['thread_id']}.json"
        evidence_summary = {}
        for key, ev_list in result.get('evidences', {}).items():
            try:
                evidence_summary[key] = [e.model_dump() if hasattr(e, 'model_dump') else str(e) for e in ev_list]
            except:
                evidence_summary[key] = [str(e) for e in ev_list]
        
        with open(evidence_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_summary, f, indent=2)
    
    def _display_audit_summary(self, result: Dict[str, Any], report_path: Path, is_peer: bool = False):
        """Display audit summary"""
        console.print("\n[bold green]✅ Audit Complete![/bold green]")
        
        # Extract scores from final report
        final_report = result.get('final_report', '')
        
        # Parse scores (simple parsing)
        scores = []
        for line in final_report.split('\n'):
            if '| **' in line and '** | **' in line:
                parts = line.split('|')
                if len(parts) >= 3:
                    criterion = parts[1].strip().strip('*')
                    score = parts[2].strip().strip('*')
                    scores.append((criterion, score))
        
        if scores:
            table = Table(title="Audit Results")
            table.add_column("Criterion", style="cyan")
            table.add_column("Score", style="green", justify="center")
            
            for criterion, score in scores[:5]:  # Show first 5
                table.add_row(criterion, score)
            
            console.print(table)
        
        console.print(f"\n[bold]Report saved to:[/bold] {report_path}")
        
        # Ask if they want to view full report
        if questionary.confirm("View full report?").ask():
            self._display_report(report_path)
    
    def _display_report(self, report_path: Path):
        """Display markdown report"""
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        md = Markdown(content)
        console.print(md)
    
    def _display_received_report(self, report_path: Path):
        """Display received report with metadata"""
        # Try to load metadata
        metadata_path = report_path.with_suffix('.json')
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            console.print(Panel.fit(
                f"[bold magenta]Report from: {metadata.get('peer', 'Unknown')}[/bold magenta]\n"
                f"Received: {metadata.get('received_at', 'Unknown')}",
                title="Report Metadata"
            ))
        
        # Display report
        self._display_report(report_path)
    
    def _display_comparison(self, self_path: Path, peer_path: Path):
        """Compare self audit with peer audit"""
        console.print("\n[bold blue]📊 Audit Comparison[/bold blue]")
        
        # Load reports
        with open(self_path, 'r', encoding='utf-8') as f:
            self_content = f.read()
        
        with open(peer_path, 'r', encoding='utf-8') as f:
            peer_content = f.read()
        
        # Simple comparison table
        table = Table(title="Self vs Peer Audit Comparison")
        table.add_column("Metric", style="cyan")
        table.add_column("Self Audit", style="green")
        table.add_column("Peer Audit", style="yellow")
        
        # Extract file sizes
        self_size = self_path.stat().st_size
        peer_size = peer_path.stat().st_size
        
        table.add_row("File Size", f"{self_size/1024:.1f} KB", f"{peer_size/1024:.1f} KB")
        table.add_row("Report Length", f"{len(self_content)} chars", f"{len(peer_content)} chars")
        
        console.print(table)
        
        # Show differences
        if questionary.confirm("Show detailed differences?").ask():
            console.print("\n[bold]Self Audit Preview:[/bold]")
            console.print(self_content[:500] + "...\n")
            
            console.print("[bold]Peer Audit Preview:[/bold]")
            console.print(peer_content[:500] + "...")


def main():
    """Main interactive loop"""
    manager = AuditManager()
    
    console.print(Panel.fit(
        "[bold cyan]🤖 Automaton Auditor - Week 2 Challenge[/bold cyan]\n"
        "[dim]Digital Courtroom for Autonomous Code Governance[/dim]",
        border_style="bright_blue"
    ))
    
    while True:
        choice = manager.select_audit_type()
        
        if "Exit" in choice:
            console.print("[yellow]Goodbye! 👋[/yellow]")
            break
        
        elif "MY OWN" in choice:
            manager.display_header("Self-Audit Mode")
            repo_info = manager.get_repo_info()
            pdf_path = manager.get_pdf_path()
            manager.run_self_audit(repo_info["url"], pdf_path)
        
        elif "PEER'S" in choice:
            manager.display_header("Peer Audit Mode")
            repo_info = manager.get_repo_info()
            if not repo_info["is_peer"]:
                console.print("[red]Please confirm this is a peer's repository.[/red]")
                continue
            
            pdf_path = manager.get_pdf_path()
            manager.run_peer_audit(repo_info["url"], pdf_path, repo_info["peer_name"])
        
        elif "View/Manage" in choice:
            manager.display_header("Received Reports")
            
            subchoice = questionary.select(
                "What would you like to do?",
                choices=[
                    "View all received reports",
                    "Receive a new peer report",
                    "Back to main menu"
                ]
            ).ask()
            
            if "View all" in subchoice:
                manager.view_received_reports()
            elif "Receive" in subchoice:
                manager.receive_peer_report()
        
        elif "Compare" in choice:
            manager.compare_audits()
        
        # Ask to continue
        if not questionary.confirm("Run another audit?", default=True).ask():
            console.print("[yellow]Goodbye! 👋[/yellow]")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user. Goodbye! 👋[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error: {str(e)}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)