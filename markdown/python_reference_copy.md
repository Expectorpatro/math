# Python Object References and Copying Summary

This document summarizes Python behaviors and mechanisms regarding references, assignment, NumPy `asarray`, and the `copy` module.

## 1. `self` and Instance Attribute Assignment

```python
class A:
    def __init__(self):
        self.x = None

a = A()
lst = [1,2,3]
a.x = lst  # self.x binds to the reference of lst
```

* `self` is a reference to the instance object.
* `self.attr = ...` binds an attribute to an object reference; it does not create a new object.
* Modifying `self.x` will affect `lst` because they reference the same object.

## 2. Assignment with `=` Operator

* Plain assignment `=` **always binds a reference**, without creating a new object.
* Example:

```python
a = [1,2,3]
b = a  # b references a
b.append(4)
print(a)  # [1,2,3,4]
```

* Cases where a new object is created:

  * Function returns a new object (e.g., `copy.deepcopy()`, `np.array()`)
  * Expression results produce new objects (e.g., `a + [4]`)

## 3. NumPy `np.asarray()` vs `np.array()`

```python
import numpy as np

a = np.array([1,2,3])
b = np.asarray(a)  # references a
b[0] = 100
print(a)  # [100,2,3]

lst = [1,2,3]
c = np.asarray(lst)  # new ndarray
c[0] = 100
print(lst)  # [1,2,3]
```

* **np.asarray(x)**

  * Input is ndarray → does not create a new object, returns original reference
  * Input is list/tuple → creates a new ndarray
* **np.array(x)**

  * Always creates a new ndarray

## 4. Python `copy` Module

```python
import copy

a = [1, [2,3]]

shallow = copy.copy(a)   # shallow copy
deep = copy.deepcopy(a)  # deep copy
```

| Method          | Object Type              | Copy Depth | Description                                        |
| --------------- | ------------------------ | ---------- | -------------------------------------------------- |
| copy.copy()     | list/dict/custom objects | Shallow    | Top-level object is new, nested objects are shared |
| copy.deepcopy() | list/dict/custom objects | Deep       | Both top-level and nested objects are new          |

Example:

```python
shallow[1][0] = 200
print(a)  # [1, [200,3]]  # nested list shared

deep[1][0] = 300
print(a)  # [1, [200,3]]  # fully independent
```

## 5. Assignment and Reference Summary Table

| Operation        | New Object Created? | Data Shared?                  | Notes                                    |
| ---------------- | ------------------- | ----------------------------- | ---------------------------------------- |
| b = a            | ❌                   | ✅                             | Only reference binding                   |
| np.asarray(a)    | Depends on input    | ndarray input → ✅, others → ❌ | ndarray input does not create new object |
| np.array(a)      | ✅                   | ❌                             | Always creates new ndarray               |
| copy.copy(a)     | ✅ (top-level)       | ❌ (nested shared)             | Shallow copy                             |
| copy.deepcopy(a) | ✅                   | ❌                             | Deep copy                                |
| self.attr = ...  | ❌                   | ✅                             | Attribute bound to object reference      |
