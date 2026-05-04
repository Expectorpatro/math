#include "Vector.hpp"

template <typename T>
class Queue : public Vector<T>
{
public:
    void enqueue(T const &e)
    {
        insert(_size, e);
    }

    void dequeue(){
        remove(0, 1)}

    T &front()
    {
        return (*this)[0];
    }
};