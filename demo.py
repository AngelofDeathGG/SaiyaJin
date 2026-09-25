import time, random

def quicksort(a):
    if len(a) <= 1:
        return a
    p = a[0]
    return quicksort([x for x in a[1:] if x <= p]) + [p] + quicksort([x for x in a[1:] if x > p])

def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

if __name__ == "__main__":
    t0 = time.perf_counter()
    data = [random.randint(0, 10000) for _ in range(5000)]
    assert quicksort(data) == sorted(data)
    assert fib(20) == 6765
    dt = (time.perf_counter() - t0) * 1000
    print(f"OK: sort+fib en {dt:.1f}ms")
