"""
Evaluator for the sorting optimization example.

This evaluator runs the sorting program and scores it based on:
1. Correctness (must sort correctly)
2. Performance (execution time)
3. Scalability (performance on different array sizes)
"""

import sys
import subprocess
import re


def evaluate(program_path: str) -> dict:
    """
    Evaluate the sorting program.
    
    Args:
        program_path: Path to the program to evaluate
        
    Returns:
        Dictionary with:
            - metrics: dict with 'combined_score' and other metrics
            - artifacts: dict with additional information
    """
    try:
        # Run the program and capture output
        result = subprocess.run(
            [sys.executable, program_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            # Program failed
            return {
                'metrics': {'combined_score': 0.0},
                'artifacts': {'error': result.stderr}
            }
        
        output = result.stdout
        
        # Check for correctness errors
        if 'ERROR' in output:
            return {
                'metrics': {'combined_score': 0.0},
                'artifacts': {'error': 'Sorting correctness error'}
            }
        
        # Parse timing information
        times = []
        for line in output.split('\n'):
            if 'Size' in line and 'ms' in line:
                # Extract time in milliseconds
                match = re.search(r'(\d+\.\d+)\s*ms', line)
                if match:
                    times.append(float(match.group(1)))
        
        # Extract total time
        total_time = None
        for line in output.split('\n'):
            if 'Total time:' in line:
                match = re.search(r'(\d+\.\d+)\s*ms', line)
                if match:
                    total_time = float(match.group(1))
                    break
        
        if total_time is None or not times:
            return {
                'metrics': {'combined_score': 0.0},
                'artifacts': {'error': 'Could not parse timing information'}
            }
        
        # Calculate performance score
        # Baseline: bubble sort takes ~1000ms total for our test sizes
        # Better algorithms should be much faster
        baseline_time = 1000.0  # ms
        
        # Score based on speedup over baseline
        # Score = 1 / (1 + time/baseline)
        # Fast algorithms (time << baseline) get scores near 1.0
        # Slow algorithms (time >> baseline) get scores near 0.0
        performance_score = baseline_time / (baseline_time + total_time)
        
        # Check scalability by looking at time growth
        # Good algorithms should have sub-quadratic growth
        if len(times) >= 2:
            # Compare first and last timing
            size_ratio = 10.0  # 500/50 = 10x size increase
            time_ratio = times[-1] / times[0] if times[0] > 0 else float('inf')
            
            # For O(n²): 10x size → 100x time
            # For O(n log n): 10x size → ~33x time
            # For O(n): 10x size → 10x time
            # Score based on how close to linear we are
            ideal_ratio = size_ratio  # Linear growth
            worst_ratio = size_ratio ** 2  # Quadratic growth
            
            if time_ratio <= ideal_ratio:
                scalability_score = 1.0
            elif time_ratio >= worst_ratio:
                scalability_score = 0.0
            else:
                # Linear interpolation between ideal and worst
                scalability_score = 1.0 - (time_ratio - ideal_ratio) / (worst_ratio - ideal_ratio)
        else:
            scalability_score = 0.5
        
        # Combined score (weighted average)
        combined_score = 0.6 * performance_score + 0.4 * scalability_score
        
        return {
            'metrics': {
                'combined_score': float(combined_score),
                'performance_score': float(performance_score),
                'scalability_score': float(scalability_score),
                'total_time_ms': float(total_time)
            },
            'artifacts': {
                'individual_times': times,
                'output': output
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            'metrics': {'combined_score': 0.0},
            'artifacts': {'error': 'Program timed out (too slow)'}
        }
    except Exception as e:
        return {
            'metrics': {'combined_score': 0.0},
            'artifacts': {'error': str(e)}
        }
