using Rank = int;

template <typename T>
struct ListNode
{
    T data{};
    ListNode<T> *pred{nullptr};
    ListNode<T> *succ{nullptr};

    ListNode() = default;

    ListNode(const T &e, ListNode<T> *p = nullptr, ListNode<T> *s = nullptr)
        : data(e), pred(p), succ(s) {};
};

template <typename T>
class List
{
private:
    int _size;
    ListNode<T> *header;
    ListNode<T> *trailer;

protected:
    void init();
    void copyNodes(ListNode<T> *p, int n);

public:
    List();
    List(const List<T> &L);
    List(const List<T> &L, int r, int n);
    List(ListNode<T> *p, int n);
    ~List();

    Rank size() const;
    bool empty() const;
    const ListNode<T> *first() const;
    T &operator[](Rank r);
    const T &operator[](Rank r) const;

    const ListNode<T> *find(T const &e, ListNode<T> *p, int n) const;

    void insertAsFirst(T const &e);
    void insertAsLast(T const &e);
    void insertAfter(ListNode<T> *p, const T &e);
    void insertBefore(ListNode<T> *p, const T &e);
    void remove(ListNode<T> *p)
};

template <typename T>
void List<T>::init()
{
    header = new ListNode<T>;
    trailer = new ListNode<T>;
    header->succ = trailer;
    header->pred = nullptr;
    trailer->pred = header;
    trailer->succ = nullptr;
    _size = 0;
}

template <typename T>
void List<T>::copyNodes(ListNode<T> *p, int n)
{
    init();
    while (n--)
    {
        insertAsLast(p->data);
        p = p->succ;
    }
}

template <typename T>
List<T>::List()
{
    init();
}

template <typename T>
List<T>::List(const List<T> &L)
{
    copyNodes(L.first(), L._size);
}

template <typename T>
List<T>::List(const List<T> &L, int r, int n)
{
    copyNodes(L[r], n);
}

template <typename T>
List<T>::List(ListNode<T> *p, int n)
{
    copyNodes(p, n);
}

template <typename T>
List<T>::~List()
{
    while (0 < _size)
    {
        remove(header->succ);
    }
    delete header;
    delete trailer;
}

template <typename T>
Rank List<T>::size() const
{
    return _size;
}

template <typename T>
bool List<T>::empty() const
{
    return _size == 0;
}

template <typename T>
const ListNode<T> *List<T>::first() const
{
    return header->succ;
}

template <typename T>
T &List<T>::operator[](Rank r)
{
    ListNode<T> *p{first()};
    while (0 < r--)
    {
        p = p->succ
    }

    return p->data;
}

template <typename T>
const T &List<T>::operator[](Rank r) const
{
    ListNode<T> *p{first()};
    while (0 < r--)
    {
        p = p->succ
    }

    return p->data;
}

template <typename T>
const ListNode<T> *List<T>::find(T const &e, ListNode<T> *p, int n) const
{
    while (0 < n--)
    {
        p = p->pred;
        if (e == p->data)
            return p;
    }
    return nullptr;
}

template <typename T>
void List<T>::insertAsFirst(T const &e)
{
    _size++;
    ListNode<T> *x = new ListNode<T>(e, header, header->succ);
    header->succ->pred = x;
    header->succ = x;
}

template <typename T>
void List<T>::insertAsLast(T const &e)
{
    _size++;
    ListNode<T> *x = new ListNode<T>(e, trailer->pred, trailer);
    trailer->pred->succ = x;
    trailer->pred = x;
}

template <typename T>
void List<T>::insertAfter(ListNode<T> *p, const T &e)
{
    _size++;
    ListNode<T> *x = new ListNode<T>(e, p, p->succ);
    p->succ->pred = x;
    p->succ = x;
}

template <typename T>
void List<T>::insertBefore(ListNode<T> *p, const T &e)
{
    _size++;
    ListNode<T> *x = new ListNode<T>(e, p->pred, p);
    p->pred->succ = x;
    p->pred = x;
}

template <typename T>
void List<T>::remove(ListNode<T> *p)
{
    p->pred->succ = p->succ;
    p->succ->pred = p->pred;
    delete p;
    _size--;
}