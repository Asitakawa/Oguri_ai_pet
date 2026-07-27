import random
def execute(max_val: int = 100, min_val: int = 0, count: int = 1, _pet=None) -> str:
    lo, hi = int(min_val), int(max_val)
    if lo > hi: lo, hi = hi, lo
    n = max(1, min(50, int(count)))
    if n == 1:
        return f"随机数: {random.randint(lo, hi)}"
    return f"随机数: {'、'.join(str(random.randint(lo, hi)) for _ in range(n))}"
