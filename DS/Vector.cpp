#include <cstdlib>

using Rank = int;

template <typename T>
class Vector
{
private:
    static constexpr int DEFAULT_CAPACITY{3};

    Rank _size{};
    int _capacity{};
    T *_elem{};

    void copyFrom(const T *A, Rank lo, Rank hi);
    void expand();
    void shrink();
    void merge(Rank lo, Rank mid, Rank hi);

public:
    Vector(int c = DEFAULT_CAPACITY, int s = 0, T v = T{});
    Vector(const T *arr, Rank lo, Rank hi);
    Vector(const Vector<T> &V);
    Vector(const Vector<T> &V, Rank lo, Rank hi);
    ~Vector();

    Vector<T> &operator=(const Vector<T> &V);

    Rank size() const;
    bool empty() const;
    T &operator[](Rank r);
    const T &operator[](Rank r) const;

    Rank find(const T &e, Rank lo, Rank hi) const;
    Rank binSearch(const T &e, Rank lo, Rank hi) const;

    void insert(const T &e, Rank r);
    void remove(Rank lo, Rank hi);

    template <typename VST>
    void traverse(VST &visit);

    bool disordered() const;
    void unsort(Rank lo, Rank hi);
    void permute();

    void bubbleSort(Rank lo, Rank hi);
    void mergeSort(Rank lo, Rank hi);

    void deduplicate();
    void uniquify();
};

template <typename T>
void Vector<T>::copyFrom(const T *A, Rank lo, Rank hi)
{
    Rank n{hi - lo};
    _capacity = (2 * n > DEFAULT_CAPACITY) ? 2 * n : DEFAULT_CAPACITY;
    _elem = new T[_capacity];
    _size = 0;

    while (lo < hi)
        _elem[_size++] = A[lo++];
}

template <typename T>
void Vector<T>::expand()
{
    if (_size < _capacity)
        return;

    T *oldElem{_elem};
    _capacity = (_capacity < DEFAULT_CAPACITY) ? DEFAULT_CAPACITY : _capacity;
    _capacity <<= 1;
    _elem = new T[_capacity];

    for (Rank i{0}; i < _size; i++)
        _elem[i] = oldElem[i];

    delete[] oldElem;
}

template <typename T>
void Vector<T>::shrink()
{
    if (_capacity <= DEFAULT_CAPACITY)
        return;
    if ((_size << 2) > _capacity)
        return;

    T *oldElem{_elem};
    _capacity >>= 1;
    if (_capacity < DEFAULT_CAPACITY)
        _capacity = DEFAULT_CAPACITY;
    _elem = new T[_capacity];

    for (Rank i{0}; i < _size; i++)
        _elem[i] = oldElem[i];

    delete[] oldElem;
}

template <typename T>
void Vector<T>::merge(Rank lo, Rank mid, Rank hi)
{
    Rank leftSize{mid - lo};
    T *leftBuf{new T[leftSize]};

    for (Rank i{0}; i < leftSize; i++)
        leftBuf[i] = _elem[lo + i];

    Rank left{0};
    Rank right{mid};
    Rank dest{lo};

    while (left < leftSize && right < hi)
    {
        if (leftBuf[left] <= _elem[right])
            _elem[dest++] = leftBuf[left++];
        else
            _elem[dest++] = _elem[right++];
    }

    while (left < leftSize)
        _elem[dest++] = leftBuf[left++];

    delete[] leftBuf;
}

template <typename T>
Vector<T>::Vector(int c, int s, T v)
    : _size{0},
      _capacity{(c > DEFAULT_CAPACITY) ? c : DEFAULT_CAPACITY},
      _elem{new T[_capacity]}
{
    while (_size < s)
        _elem[_size++] = v;
}

template <typename T>
Vector<T>::Vector(const T *arr, Rank lo, Rank hi)
{
    copyFrom(arr, lo, hi);
}

template <typename T>
Vector<T>::Vector(const Vector<T> &V)
{
    copyFrom(V._elem, 0, V._size);
}

template <typename T>
Vector<T>::Vector(const Vector<T> &V, Rank lo, Rank hi)
{
    copyFrom(V._elem, lo, hi);
}

template <typename T>
Vector<T>::~Vector()
{
    delete[] _elem;
}

template <typename T>
Vector<T> &Vector<T>::operator=(const Vector<T> &V)
{
    if (this == &V)
        return *this;

    delete[] _elem;
    copyFrom(V._elem, 0, V._size);
    return *this;
}

template <typename T>
Rank Vector<T>::size() const
{
    return _size;
}

template <typename T>
bool Vector<T>::empty() const
{
    return _size == 0;
}

template <typename T>
T &Vector<T>::operator[](Rank r)
{
    return _elem[r];
}

template <typename T>
const T &Vector<T>::operator[](Rank r) const
{
    return _elem[r];
}

template <typename T>
Rank Vector<T>::find(const T &e, Rank lo, Rank hi) const
{
    while ((lo < hi--) && (e != _elem[hi]))
        ;
    return hi;
}

template <typename T>
Rank Vector<T>::binSearch(const T &e, Rank lo, Rank hi) const
{
    while (lo < hi)
    {
        Rank mi{lo + ((hi - lo) >> 1)};

        if (_elem[mi] < e)
            lo = mi + 1;
        else if (e < _elem[mi])
            hi = mi;
        else
            return mi;
    }

    return -1;
}

template <typename T>
void Vector<T>::insert(const T &e, Rank r)
{
    expand();
    for (Rank i{_size}; i > r; i--)
        _elem[i] = _elem[i - 1];
    _elem[r] = e;
    _size++;
}

template <typename T>
void Vector<T>::remove(Rank lo, Rank hi)
{
    if (lo >= hi)
        return;

    while (hi < _size)
        _elem[lo++] = _elem[hi++];

    _size = lo;
    shrink();
}

template <typename T>
template <typename VST>
void Vector<T>::traverse(VST &visit)
{
    for (Rank i{0}; i < _size; i++)
        visit(_elem[i]);
}

template <typename T>
bool Vector<T>::disordered() const
{
    for (Rank i{0}; i < _size - 1; i++)
    {
        if (_elem[i] > _elem[i + 1])
            return true;
    }
    return false;
}

template <typename T>
void Vector<T>::unsort(Rank lo, Rank hi)
{
    T *V{_elem + lo};

    for (Rank i{hi - lo}; i > 0; i--)
    {
        Rank j{rand() % i};
        T temp{V[i - 1]};
        V[i - 1] = V[j];
        V[j] = temp;
    }
}

template <typename T>
void Vector<T>::permute()
{
    unsort(0, _size);
}

template <typename T>
void Vector<T>::bubbleSort(Rank lo, Rank hi)
{
    for (Rank end{hi}; end > lo + 1; end--)
    {
        bool swapped{false};

        for (Rank i{lo + 1}; i < end; i++)
        {
            if (_elem[i - 1] > _elem[i])
            {
                T temp{_elem[i - 1]};
                _elem[i - 1] = _elem[i];
                _elem[i] = temp;
                swapped = true;
            }
        }

        if (!swapped)
            return;
    }
}

template <typename T>
void Vector<T>::mergeSort(Rank lo, Rank hi)
{
    if (hi - lo < 2)
        return;

    Rank mid{lo + ((hi - lo) >> 1)};
    mergeSort(lo, mid);
    mergeSort(mid, hi);

    if (_elem[mid - 1] <= _elem[mid])
        return;

    merge(lo, mid, hi);
}

template <typename T>
void Vector<T>::deduplicate()
{
    Rank i{1};
    while (i < _size)
    {
        if (find(_elem[i], 0, i) < 0)
            i++;
        else
            remove(i, i + 1);
    }
}

template <typename T>
void Vector<T>::uniquify()
{
    if (_size < 2)
        return;

    Rank writeIndex{0};
    for (Rank readIndex{1}; readIndex < _size; readIndex++)
    {
        if (_elem[readIndex] != _elem[writeIndex])
            _elem[++writeIndex] = _elem[readIndex];
    }

    _size = writeIndex + 1;
    shrink();
}
