#include "Vector.hpp"

template <typename T>
class Stack : public Vector<T>
{
public:
    void push(T const &e)
    {
        insert(_size, e);
    }

    void pop()
    {
        remove(_size - 1, _size);
    }

    T &top()
    {
        return (*this)[size() - 1];
    }
};