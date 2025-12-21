#!/usr/bin/env python3
"""
Plot metrics from optimization output programs.
Usage:
  python plot_optimization_metrics.py [path_to_programs_folder] [--metric1 METRIC] [--metric2 METRIC] [--openevolve PATH]

Examples:
  python plot_optimization_metrics.py programs/
  python plot_optimization_metrics.py programs/ --metric1 combined_score
  python plot_optimization_metrics.py programs/ --metric1 combined_score --metric2 eval_time
  python plot_optimization_metrics.py programs/ --openevolve examples/function_minimization/openevolve_output/checkpoints/checkpoint_25/programs
"""

import argparse
import json
import re
import sys
from pathlib import Path
import matplotlib.pyplot as plt


def parse_evaluation_file(filepath):
    """Parse an evaluation file and extract metrics."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    metrics = {}
    # Extract only the Metrics section
    metrics_section = re.search(r'Metrics:\s*\n((?:\s+\w+:\s+[\d.]+\s*\n)+)', content)
    
    if metrics_section:
        metrics_text = metrics_section.group(1)
        # Extract metrics using regex - now only from the Metrics section
        metric_pattern = r'(\w+):\s+([\d.]+)'
        for match in re.finditer(metric_pattern, metrics_text):
            metric_name = match.group(1)
            metric_value = float(match.group(2))
            metrics[metric_name] = metric_value
    
    return metrics


def collect_metrics_openevolve(programs_dir):
    """Collect metrics from OpenEvolve JSON files."""
    programs_path = Path(programs_dir)
    
    # Find all JSON files
    json_files = sorted(programs_path.glob('*.json'))
    
    versions = []
    all_metrics = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract iteration_found as version number
            version_num = data.get('iteration_found')
            if version_num is not None:
                versions.append(version_num)
                # Extract metrics from the metrics field
                metrics = data.get('metrics', {})
                all_metrics.append(metrics)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not parse {json_file.name}: {e}")
    
    # Sort by version number
    if versions:
        combined = sorted(zip(versions, all_metrics), key=lambda x: x[0])
        versions, all_metrics = zip(*combined)
        versions = list(versions)
        all_metrics = list(all_metrics)
    
    return versions, all_metrics


def collect_metrics(programs_dir):
    """Collect metrics from all evaluation files in the directory."""
    programs_path = Path(programs_dir)
    
    # Check if this is an OpenEvolve directory (contains JSON files)
    json_files = list(programs_path.glob('*.json'))
    if json_files:
        print(f"Detected OpenEvolve format (JSON files)")
        return collect_metrics_openevolve(programs_dir)
    
    # Otherwise, use the original format (v*.py with evaluation files)
    # Find all program files (not just evaluation files)
    program_files = sorted(programs_path.glob('v*.py'))
    
    versions = []
    all_metrics = []
    
    for program_file in program_files:
        # Extract version number from filename
        version_match = re.match(r'v(\d+)_', program_file.name)
        if version_match:
            version_num = int(version_match.group(1))
            
            # Look for corresponding evaluation file
            eval_file = program_file.with_suffix('').parent / f"{program_file.stem}_evaluation.txt"
            
            if eval_file.exists():
                versions.append(version_num)
                metrics = parse_evaluation_file(eval_file)
                all_metrics.append(metrics)
            else:
                # If no evaluation file, create placeholder with None values
                print(f"Warning: No evaluation file found for {program_file.name}")
                versions.append(version_num)
                all_metrics.append({})
    
    return versions, all_metrics


def plot_metrics(versions, all_metrics, programs_dir, metric1='combined_score', metric2=None, 
                 metric2_higher_is_better=False, oe_versions=None, oe_metrics=None, output_file=None):
    """Plot one or two metrics. If metric2 is provided, use dual y-axes.
    If oe_versions/oe_metrics provided, plot two separate lines for comparison.
    
    Args:
        metric2_higher_is_better: If True, track highest value for metric2. If False, track lowest (default).
        output_file: Path to save the plot. If None, saves to programs_dir/../metrics_plot.png
    """
    if not versions:
        print("No evaluation files found!")
        return
    
    # Extract metric1 values, treating 0 as None for failed runs
    metric1_values = [m.get(metric1, None) if m.get(metric1, None) not in (0, 0.0) else None for m in all_metrics]
    
    # Debug output
    print(f"\nDEBUG: Plotting {metric1}")
    print(f"  Versions: {versions}")
    print(f"  Values: {metric1_values}")
    print(f"  Non-None count: {sum(1 for v in metric1_values if v is not None)}")
    
    # Calculate running best for metric1 (higher is better)
    best_metric1 = []
    current_best = float('-inf')
    for val in metric1_values:
        if val is not None and val > current_best:
            current_best = val
        best_metric1.append(current_best if current_best != float('-inf') else None)
    
    # Create figure
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    # Plot first metric for main data
    color1 = 'tab:blue'
    ax1.set_xlabel('Version', fontsize=12)
    ax1.set_ylabel(metric1.replace('_', ' ').title(), color=color1, fontsize=12)
    line1 = ax1.plot(versions, metric1_values, 'o-', color=color1, linewidth=3, 
                     markersize=10, label=f'{metric1} (main)', zorder=5)
    line1_best = ax1.plot(versions, best_metric1, '--', color=color1, linewidth=2, 
                          alpha=0.8, label=f'Best {metric1} (main)', zorder=4)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, alpha=0.3, zorder=0)
    
    print(f"  ax1 y-limits: {ax1.get_ylim()}")
    
    lines = line1 + line1_best
    
    # Plot OpenEvolve data if provided
    if oe_versions and oe_metrics:
        oe_metric1_values = [m.get(metric1, None) if m.get(metric1, None) not in (0, 0.0) else None for m in oe_metrics]
        
        # Calculate running best for OpenEvolve
        oe_best_metric1 = []
        current_best = float('-inf')
        for val in oe_metric1_values:
            if val is not None and val > current_best:
                current_best = val
            oe_best_metric1.append(current_best if current_best != float('-inf') else None)
        
        color_oe = 'tab:green'
        line_oe = ax1.plot(oe_versions, oe_metric1_values, 's-', color=color_oe, linewidth=2,
                          markersize=8, label=f'{metric1} (OpenEvolve)')
        line_oe_best = ax1.plot(oe_versions, oe_best_metric1, '--', color=color_oe, linewidth=1.5,
                               alpha=0.7, label=f'Best {metric1} (OpenEvolve)')
        lines = lines + line_oe + line_oe_best
    
    # Plot second metric if provided
    if metric2:
        # Extract metric2 values, treating 0 as None for failed runs
        metric2_values = [m.get(metric2, None) if m.get(metric2, None) not in (0, 0.0) else None for m in all_metrics]
        
        print(f"\nDEBUG: Plotting {metric2}")
        print(f"  Values: {metric2_values}")
        print(f"  Non-None count: {sum(1 for v in metric2_values if v is not None)}")
        
        # Calculate running best for metric2
        best_metric2 = []
        if metric2_higher_is_better:
            # Higher is better
            current_best = float('-inf')
            for val in metric2_values:
                if val is not None and val > current_best:
                    current_best = val
                best_metric2.append(current_best if current_best != float('-inf') else None)
        else:
            # Lower is better (default)
            current_best = float('inf')
            for val in metric2_values:
                if val is not None and val < current_best:
                    current_best = val
                best_metric2.append(current_best if current_best != float('inf') else None)
        
        # Create second y-axis
        ax2 = ax1.twinx()
        color2 = 'tab:orange'
        ax2.set_ylabel(metric2.replace('_', ' ').title(), color=color2, fontsize=12)
        line2 = ax2.plot(versions, metric2_values, 'D-', color=color2, linewidth=2, 
                         markersize=7, label=metric2, alpha=0.7, zorder=3)
        best_label = f'{"Highest" if metric2_higher_is_better else "Lowest"} {metric2} so far'
        line2_best = ax2.plot(versions, best_metric2, ':', color=color2, linewidth=2,
                              alpha=0.6, label=best_label, zorder=2)
        ax2.tick_params(axis='y', labelcolor=color2)
        
        print(f"  ax2 y-limits: {ax2.get_ylim()}")
        
        lines = lines + line2 + line2_best
        
        # Plot OpenEvolve metric2 if provided
        if oe_versions and oe_metrics:
            oe_metric2_values = [m.get(metric2, None) if m.get(metric2, None) not in (0, 0.0) else None for m in oe_metrics]
            
            # Calculate running best for OpenEvolve metric2
            oe_best_metric2 = []
            if metric2_higher_is_better:
                # Higher is better
                current_best = float('-inf')
                for val in oe_metric2_values:
                    if val is not None and val > current_best:
                        current_best = val
                    oe_best_metric2.append(current_best if current_best != float('-inf') else None)
            else:
                # Lower is better (default)
                current_best = float('inf')
                for val in oe_metric2_values:
                    if val is not None and val < current_best:
                        current_best = val
                    oe_best_metric2.append(current_best if current_best != float('inf') else None)
            
            color_oe2 = 'tab:purple'
            line_oe2 = ax2.plot(oe_versions, oe_metric2_values, '^-', color=color_oe2, linewidth=2,
                               markersize=7, label=f'{metric2} (OpenEvolve)', alpha=0.7, zorder=3)
            oe_best_label = f'{"Highest" if metric2_higher_is_better else "Lowest"} {metric2} (OpenEvolve)'
            line_oe2_best = ax2.plot(oe_versions, oe_best_metric2, ':', color=color_oe2, linewidth=2,
                                    alpha=0.6, label=oe_best_label, zorder=2)
            lines = lines + line_oe2 + line_oe2_best
    
    # Add title
    plt.title('Optimization Metrics Across Program Versions', fontsize=14, fontweight='bold')
    
    # Add legend
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='lower right')
    
    # Adjust layout
    fig.tight_layout()
    
    # Save and show
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = Path(programs_dir).parent / 'metrics_plot.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {output_path}")
    
    plt.show()
    
    # Print summary for main data
    print(f"\nMetrics Summary (Main):")
    if metric2:
        print(f"{'Version':<10} {metric1:<20} {metric2:<20}")
        print("-" * 50)
        for v, m in zip(versions, all_metrics):
            val1 = m.get(metric1, 'N/A')
            val2 = m.get(metric2, 'N/A')
            print(f"v{v:02d}        {val1:<20} {val2:<20}")
    else:
        print(f"{'Version':<10} {metric1:<20}")
        print("-" * 30)
        for v, m in zip(versions, all_metrics):
            val1 = m.get(metric1, 'N/A')
            print(f"v{v:02d}        {val1:<20}")
    
    # Print summary for OpenEvolve data if provided
    if oe_versions and oe_metrics:
        print(f"\nMetrics Summary (OpenEvolve):")
        if metric2:
            print(f"{'Version':<10} {metric1:<20} {metric2:<20}")
            print("-" * 50)
            for v, m in zip(oe_versions, oe_metrics):
                val1 = m.get(metric1, 'N/A')
                val2 = m.get(metric2, 'N/A')
                print(f"v{v:02d}        {val1:<20} {val2:<20}")
        else:
            print(f"{'Version':<10} {metric1:<20}")
            print("-" * 30)
            for v, m in zip(oe_versions, oe_metrics):
                val1 = m.get(metric1, 'N/A')
                print(f"v{v:02d}        {val1:<20}")


def main():
    parser = argparse.ArgumentParser(
        description='Plot metrics from optimization output programs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plot_optimization_metrics.py programs/
  python plot_optimization_metrics.py programs/ --metric1 combined_score
  python plot_optimization_metrics.py programs/ --metric1 combined_score --metric2 eval_time
  python plot_optimization_metrics.py programs/ --openevolve /path/to/openevolve/checkpoints/checkpoint_25/programs
        """
    )
    parser.add_argument("programs_dir", help="Path to programs directory")
    parser.add_argument('--metric1', default='combined_score',
                        help='Primary metric to plot (default: combined_score)')
    parser.add_argument('--metric2', default=None,
                        help='Secondary metric to plot on second y-axis (optional)')
    parser.add_argument('--metric2-higher-is-better', action='store_true',
                        help='If set, track highest value for metric2 instead of lowest')
    parser.add_argument('--openevolve', default=None,
                        help='Path to OpenEvolve programs directory to include in analysis')
    parser.add_argument('--output', default=None,
                        help='Output file path for the plot (default: programs_dir/../metrics_plot.png)')

    args = parser.parse_args()

    print(f"Analyzing metrics from: {args.programs_dir}")

    # Collect metrics from main directory
    versions, all_metrics = collect_metrics(args.programs_dir)

    # Collect metrics from OpenEvolve directory if provided
    oe_versions = None
    oe_metrics = None
    if args.openevolve:
        print(f"\nAlso analyzing OpenEvolve metrics from: {args.openevolve}")
        oe_versions, oe_metrics = collect_metrics(args.openevolve)
        if oe_versions:
            print(f"Loaded {len(oe_versions)} versions from OpenEvolve")

    if not versions:
        print("No evaluation files found!")
        return

    # Use metric2 only if explicitly provided
    metric2 = args.metric2

    # Plot metrics
    plot_metrics(versions, all_metrics, args.programs_dir, args.metric1, metric2,
                args.metric2_higher_is_better, oe_versions, oe_metrics, args.output)


if __name__ == '__main__':
    main()
