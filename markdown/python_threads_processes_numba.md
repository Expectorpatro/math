
# Python Performance Optimization: Threads, Processes, and Numba

This document explains **threads vs processes**, **how Numba works**, and **best practices for using `@njit`**.  
It is written for readers **without a computer science background** — everything is explained clearly and intuitively.

---

## 1. Threads vs Processes

### What Is a Thread?
A **thread** is like a worker inside a program that executes tasks **within the same memory space**.

- All threads share the **same memory** (variables, arrays, etc.)
- Creating a thread is **lightweight** (fast, small memory overhead)
- Suitable for **CPU-bound tasks** that release the GIL (e.g. NumPy, Numba)
- Or **I/O-bound tasks** (e.g. waiting for files, network)

### What Is a Process?
A **process** is an independent program running in its **own memory space**.

- Each process has **its own copy** of the variables
- Communication between processes is **slow** (data must be serialized and sent through pipes)
- Creating a process is **heavier** (requires memory duplication)
- Best for **truly parallel computation** when GIL is a bottleneck

### Comparison Table

| Feature                       | Threads                         | Processes                         |
| ----------------------------- | ------------------------------- | --------------------------------- |
| Memory Sharing                | Shared                          | Independent                       |
| Creation Overhead             | Fast                            | Slow                              |
| GIL (Global Interpreter Lock) | Affects CPU tasks               | Not affected                      |
| Communication Cost            | Low                             | High                              |
| Use Case                      | I/O tasks, Numba-parallel loops | Heavy CPU tasks (multiprocessing) |

### 🧮 Example (Joblib)
```python
from joblib import Parallel, delayed
import numpy as np

def compute(x):
    return np.sqrt(x ** 2 + 1)

data = np.arange(10_000)

# Use threads for lightweight sharing
results = Parallel(n_jobs=-1, prefer="threads")(delayed(compute)(x) for x in data)
```

Here `prefer="threads"` means:
> “Run computations in multiple threads **within one process**”  
> → avoids copying large NumPy arrays between processes.

---

## ⚙️ 2. Numba: What It Is and Why It’s Fast

### 🧩 What is Numba?
**Numba** is a Just-In-Time (JIT) compiler that translates Python + NumPy code into **machine code (LLVM)** at runtime.

### ⚙️ How It Works
1. You write normal Python code.
2. The first time you call the function, Numba **inspects the types** of arguments.
3. It compiles the function to **native CPU instructions**.
4. Later calls use the compiled version directly — very fast!

### 💡 Why It’s Fast
- Skips Python interpreter overhead.
- Uses SIMD and vectorized CPU instructions.
- Eliminates dynamic typing (types are fixed at compile-time).

### 🚀 When to Use Numba
| Task                                | Numba Performance                   |
| ----------------------------------- | ----------------------------------- |
| Loops with heavy numeric operations | ✅ Excellent                         |
| Simple NumPy arithmetic             | ⚠️ Usually fast enough without Numba |
| String manipulation, lists, dicts   | ❌ Not supported                     |
| Matrix operations + math            | ✅ Huge speedups                     |

---

## 🧱 3. Using `@njit`

### ✅ Basic Example
```python
from numba import njit

@njit
def add(x, y):
    return x + y
```

### ⚡ Advanced Example
```python
@njit(fastmath=True, parallel=True)
def compute_sum(x):
    total = 0.0
    for i in range(x.size):
        total += x[i] ** 2
    return total
```
**Explanation:**
- `fastmath=True` → allows aggressive floating-point optimizations (may slightly reduce precision)
- `parallel=True` → enables multi-threading inside loops (Numba automatically distributes iterations)

---

## 🧩 4. `njit` Design Principles

### 🔹 Keep Code Simple
Numba works best when the function body is **low-level and explicit**.  
Avoid dynamic Python features (like list comprehensions, lambdas, dicts).

### 🔹 Define Functions at Top Level
`@njit` functions must be defined **at the module level** — not inside another function or class method —  
because Numba compiles functions **at import time**.

You can call them *inside* classes or functions, but **don’t define them there**.

### 🔹 Default Arguments
Numba supports **simple default values** like `None`, `int`, `float`, or NumPy arrays.

✅ Example:
```python
@njit
def func(x, y=None):
    if y is None:
        y = np.zeros_like(x)
    return x + y
```

⚠️ Avoid lists, dicts, or strings as defaults — Numba cannot compile them.

---

## 🧮 5. Example: Threaded + Numba Accelerated Function

```python
import numpy as np
from numba import njit, prange
from joblib import Parallel, delayed

@njit(fastmath=True, parallel=True)
def compute_logdet_scores_numba(X_labeled, X_unlabeled, uncertainty, probs_unlabeled, candidate, a):
    n_features = X_labeled.shape[1]
    n_labeled = X_labeled.shape[0]
    scores = np.zeros(candidate.shape[0])
    
    for idx in prange(candidate.shape[0]):  # parallel loop
        i = candidate[idx]
        x_new = X_unlabeled[i]
        p_new = probs_unlabeled[i, 1]
        u_new = p_new * (1 - p_new)
        
        # Update information matrix
        X_aug = np.vstack((X_labeled, x_new))
        uncert_aug = np.append(uncertainty, u_new)
        M = (X_aug.T @ (uncert_aug[:, None] * X_aug)) / (n_labeled + 1)
        
        # Compute log-determinant (stable & fast)
        sign, logdet = np.linalg.slogdet(M + 1e-6 * np.eye(n_features))
        scores[idx] = sign * logdet
    return scores
```

### ⚡ Why `np.linalg.slogdet`?
- `np.linalg.det(M)` computes the **determinant directly**, which can **underflow or overflow**.
- `np.linalg.slogdet(M)` returns `(sign, log(|det|))`, so it’s:
  - **Numerically stable**
  - **Faster** (avoids full matrix product for large values)

---

## 🔬 6. Summary Table

| Topic               | Key Idea                       | When to Use                    |
| ------------------- | ------------------------------ | ------------------------------ |
| Threads             | Share memory, low overhead     | Lightweight parallel loops     |
| Processes           | Separate memory, safe from GIL | Heavy CPU computation          |
| Numba               | Compile Python → machine code  | Numeric + loop-heavy functions |
| `fastmath=True`     | Allow math approximations      | Performance-critical code      |
| `parallel=True`     | Enable multi-threading         | Loops over large arrays        |
| `np.linalg.slogdet` | Stable log-determinant         | Determinant comparisons        |

---

## 🏁 7. Key Takeaways

- **Threads** share memory → efficient for NumPy-heavy code.  
- **Processes** are safer but slower due to memory duplication.  
- **Numba** transforms Python into optimized machine code.  
- Use `@njit(fastmath=True, parallel=True)` for maximum speed on numeric loops.  
- Always keep Numba code **explicit, typed, and simple**.

---

**Author:** Xingcheng Ni  
**Date:** 2025-10-15  
**Title:** *Understanding Threads, Processes, and Numba Acceleration in Python*
