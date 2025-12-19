"""
Initial program for sorting algorithm optimization example.

This program sorts arrays of integers. The goal is to evolve
a more efficient sorting implementation.

The initial implementation uses a simple bubble sort, which is
inefficient for large arrays (O(n²) time complexity).
"""

import random


def generate_test_array(size=100):
    """Generate a random array for testing."""
    return [random.randint(1, 1000) for _ in range(size)]


# EVOLVE-BLOCK-START
def sort_array(arr):
    """
    Sort an array of integers in ascending order.
    
    Current implementation: Bubble sort (inefficient!)
    """
    arr = arr.copy()  # Don't modify the original
    n = len(arr)
    
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    
    return arr
# EVOLVE-BLOCK-END


def verify_sorted(arr):
    """Verify that an array is sorted correctly."""
    for i in range(len(arr) - 1):
        if arr[i] > arr[i + 1]:
            return False
    return True


def main():
    """Run the sorting algorithm on test cases."""
    import time
    
    # Test with different array sizes
    test_sizes = [50, 100, 200, 500]
    total_time = 0
    
    for size in test_sizes:
        test_array = generate_test_array(size)
        
        start_time = time.perf_counter()
        sorted_array = sort_array(test_array)
        end_time = time.perf_counter()
        
        elapsed = end_time - start_time
        total_time += elapsed
        
        # Verify correctness
        if not verify_sorted(sorted_array):
            print(f"ERROR: Array of size {size} not sorted correctly!")
            return None
        
        print(f"Size {size:4d}: {elapsed*1000:.3f} ms")
    
    print(f"Total time: {total_time*1000:.3f} ms")
    return total_time


if __name__ == "__main__":
    main()
