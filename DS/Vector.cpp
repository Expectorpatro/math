#include <cstdlib>
using namespace std;
typedef int Rank;
#define DEFAULT_CAPACITY 3

template <typename T>
class Vector
{
protected:
    Rank _size;
    int _capacity;
    T *_elem;

    void copyFrom(const T *A, Rank lo, Rank hi)
    {
        _capacity = 2 * (hi - lo);
        _elem = new T[_capacity];
        _size = 0;

        while (lo < hi)
        {
            _elem[_size] = A[lo];
            _size++;
            lo++;
        }
    }

public:
    Vector(int c = DEFAULT_CAPACITY, int s = 0, T v = 0)
    {
        _capacity = c;
        _elem = new T[_capacity];
        _size = 0;

        while (_size < s)
        {
            _elem[_size] = v;
            _size++;
        }
    }

    Vector(const T *arr, Rank lo, Rank hi)
    {
        copyFrom(arr, lo, hi);
    }

    Vector(const Vector<T> &V)
    {
        copyFrom(V._elem, 0, V._size);
    }

    Vector(const Vector<T> &V, Rank lo, Rank hi)
    {
        copyFrom(V._elem, lo, hi);
    }

    ~Vector()
    {
        delete[] _elem;
    }

    Vector<T> &operator=(const Vector<T> &V)
    {
        if (this == &V)
            return *this;

        delete[] _elem;
        copyFrom(V._elem, 0, V._size);
        return *this;
    }

    Rank size() const
    {
        return _size;
    }

    bool empty() const
    {
        return _size == 0;
    }

    T &operator[](Rank r)
    {
        return _elem[r];
    }

    Rank find(const T &e, Rank lo, Rank hi) const
    {
        while ((lo < hi--) && (e != _elem[hi]))
            ;
        return hi;
    }

    void expand()
    {
        if (_size < _capacity)
            return;

        T *oldElem = _elem;
        _capacity <<= 1;
        _elem = new T[_capacity];
        for (Rank i = 0; i < _size; i++)
            _elem[i] = oldElem[i];
        delete[] oldElem;
    }

    void shrink()
    {
        if (_size << 2 > _capacity)
            return;

        T *oldElem = _elem;
        _capacity >>= 1;
        _elem = new T[_capacity];
        for (Rank i = 0; i < _size; i++)
            _elem[i] = oldElem[i];
        delete[] oldElem;
    }

    void insert(const T &e, Rank r)
    {
        expand();
        for (Rank i = _size; i > r; i--)
            _elem[i] = _elem[i - 1];
        _elem[r] = e;
        _size++;
    }

    void remove(Rank lo, Rank hi)
    {
        while (hi < _size)
        {
            _elem[lo] = _elem[hi];
            lo++;
            hi++;
        }
        _size = lo;
        shrink();
    }

    template <typename VST>
    void traverse(VST &visit)
    {
        for (int i = 0; i < _size; ++i)
        {
            visit(_elem[i]);
        }
    }

    bool disordered() const
    {
        for (int i = 0; i < _size - 1; i++)
        {
            if (_elem[i] > _elem[i + 1])
                return true;
        }
        return false;
    }

    void unsort(Rank lo, Rank hi)
    {
        T *V = _elem + lo;
        T temp;

        for (Rank i = hi - lo; i > 0; i--)
        {
            Rank j = rand() % i;
            temp = V[i - 1];
            V[i - 1] = V[j];
            V[j] = temp;
        }
    }

    void permute()
    {
        unsort(0, _size);
    }

    void bubbleSort(Rank lo, Rank hi)
    {
        for (Rank end = hi; end > lo + 1; end--)
        {
            bool swapped = false;

            for (Rank i = lo + 1; i < end; i++)
            {
                if (_elem[i - 1] > _elem[i])
                {
                    T temp = _elem[i - 1];
                    _elem[i - 1] = _elem[i];
                    _elem[i] = temp;
                    swapped = true;
                }
            }

            if (!swapped)
            {
                return;
            }
        }
    }

    void merge(Rank lo, Rank mid, Rank hi)
    {
        Rank leftSize = mid - lo;
        T *leftBuf = new T[leftSize];

        for (Rank i = 0; i < leftSize; i++)
        {
            leftBuf[i] = _elem[lo + i];
        }

        Rank i = 0;
        Rank j = mid;
        Rank k = lo;

        while (i < leftSize && j < hi)
        {
            if (leftBuf[i] <= _elem[j])
            {
                _elem[k++] = leftBuf[i++];
            }
            else
            {
                _elem[k++] = _elem[j++];
            }
        }

        while (i < leftSize)
        {
            _elem[k++] = leftBuf[i++];
        }

        delete[] leftBuf;
    }

    void mergeSort(Rank lo, Rank hi)
    {
        if (hi - lo < 2)
        {
            return;
        }

        Rank mid = (hi + lo) >> 1;

        mergeSort(lo, mid);
        mergeSort(mid, hi);

        if (_elem[mid - 1] <= _elem[mid])
        {
            return;
        }

        merge(lo, mid, hi);
    }

    void deduplicate()
    {
        Rank i = 1;
        while (i < _size)
            (find(_elem[i], 0, i) < 0) ? i++ : remove(i, i + 1);
    }

    void uniquify()
    {
        Rank write_index = 0;

        for (Rank read_index = 1; read_index < _size; read_index++)
        {
            if (_elem[read_index] != _elem[write_index])
            {
                write_index = write_index + 1;
                _elem[write_index] = _elem[read_index];
            }
        }

        _size = write_index + 1;
        shrink();
    }

    Rank binSearch(const T &e, Rank lo, Rank hi) const
    {
        while (1 < hi - lo)
        {
            Rank mi = (hi + lo) >> 1;

            if (_elem[mi] < e)
            {
                lo = mi + 1;
            }
            else
            {
                hi = mi;
            }
        }
        return (e == _elem[lo]) ? lo : -1;
    }
};
