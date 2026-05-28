#include <algorithm>

template <typename T>
class BinNode
{
    T _data;
    BinNode<T> *_parent;
    BinNode<T> *_lChild;
    BinNode<T> *_rChild;
    int _depth;
    int _height;

public:
    BinNode(const T &e, BinNode<T> *p = nullptr)
        : _data(e),
          _parent(p),
          _lChild(nullptr),
          _rChild(nullptr),
          _depth(p ? p->_depth + 1 : 0),
          _height(0)
    {
    }

    ~BinNode() = default;

    void insertAsLC(const T &e);
    void insertAsRC(const T &e);

    bool isRoot() const;
    bool hasParent() const;
    bool isLChild() const;
    bool isRChild() const;
    bool hasLChild() const;
    bool hasRChild() const;
    bool hasChild() const;
    bool hasBothChild() const;
    bool isLeaf() const;
};

template <typename T>
inline bool BinNode<T>::isRoot() const
{
    return _parent == nullptr;
}

template <typename T>
inline bool BinNode<T>::hasParent() const
{
    return !isRoot();
}

template <typename T>
inline bool BinNode<T>::isLChild() const
{
    return !isRoot() && this == _parent->_lChild;
}

template <typename T>
inline bool BinNode<T>::isRChild() const
{
    return !isRoot() && this == _parent->_rChild;
}

template <typename T>
inline bool BinNode<T>::hasLChild() const
{
    return _lChild != nullptr;
}

template <typename T>
inline bool BinNode<T>::hasRChild() const
{
    return _rChild != nullptr;
}

template <typename T>
inline bool BinNode<T>::hasChild() const
{
    return hasLChild() || hasRChild();
}

template <typename T>
inline bool BinNode<T>::hasBothChild() const
{
    return hasLChild() && hasRChild();
}

template <typename T>
inline bool BinNode<T>::isLeaf() const
{
    return !hasChild();
}

template <typename T>
void BinNode<T>::insertAsLC(const T &e)
{
    BinNode<T> *newNode = new BinNode<T>(e, this);
    _lChild = newNode;
}

template <typename T>
void BinNode<T>::insertAsRC(const T &e)
{
    BinNode<T> *newNode = new BinNode<T>(e, this);
    _rChild = newNode;
}

template <typename T>
class BinTree
{
public:
    int _size;
    BinNode<T> *_root;

    BinTree();
    ~BinTree();

    int getHeight(BinNode<T> *x) const;
    void updateHeight(BinNode<T> *x);
    void updateHeightAbove(BinNode<T> *x);

    void insertAsRoot(const T &e);
    void insertAsLC(BinNode<T> *x, const T &e);
    void insertAsRC(BinNode<T> *x, const T &e);
    void attachAsLC(BinNode<T> *x, BinTree<T> &S);
    void attachAsRC(BinNode<T> *x, BinTree<T> &S);

    void BinTree<T>::remove(BinNode<T> *x);
    BinTree<T> *secede(BinNode<T> *x);

    template <typename VST>
    void travPreAt(BinNode<T> *x, VST &visit);
    template <typename VST>
    void travInAt(BinNode<T> *x, VST &visit);
    template <typename VST>
    void travPostAt(BinNode<T> *x, VST &visit);

private:
    void removeAt(BinNode<T> *x);
    int countNodes(BinNode<T> *x) const;
    void updateDepthBelow(BinNode<T> *x);
};

template <typename T>
BinTree<T>::BinTree()
    : _size(0),
      _root(nullptr)
{
}

template <typename T>
BinTree<T>::~BinTree()
{
    removeAt(_root);
    _root = nullptr;
    _size = 0;
}

template <typename T>
int BinTree<T>::getHeight(BinNode<T> *x) const
{
    if (x == nullptr)
    {
        return -1;
    }

    return x->height;
}

template <typename T>
void BinTree<T>::updateHeight(BinNode<T> *x)
{
    int leftHeight = getHeight(x->lChild);
    int rightHeight = getHeight(x->rChild);

    x->height = 1 + std::max(leftHeight, rightHeight);
}

template <typename T>
void BinTree<T>::updateHeightAbove(BinNode<T> *x)
{
    while (x != nullptr)
    {
        int oldHeight = x->height;

        updateHeight(x);

        if (x->height == oldHeight)
        {
            break;
        }

        x = x->parent;
    }
}

template <typename T>
void BinTree<T>::insertAsRoot(const T &e)
{
    _size = 1;
    _root = new BinNode<T>(e);
}

template <typename T>
void BinTree<T>::insertAsLC(BinNode<T> *x, const T &e)
{
    _size++;
    x->insertAsLC(e);
    updateHeightAbove(x);
}

template <typename T>
void BinTree<T>::insertAsRC(BinNode<T> *x, const T &e)
{
    _size++;
    x->insertAsRC(e);
    updateHeightAbove(x);
}

template <typename T>
void BinTree<T>::attachAsLC(BinNode<T> *x, BinTree<T> &S)
{
    x->lChild = S._root;
    x->lChild->parent = x;
    _size += S._size;
    updateHeightAbove(x);

    S._root = nullptr;
}

template <typename T>
void BinTree<T>::attachAsRC(BinNode<T> *x, BinTree<T> &S)
{
    x->rChild = S._root;
    x->rChild->parent = x;
    _size += S._size;
    updateHeightAbove(x);

    S.root = nullptr;
}

template <typename T>
void BinTree<T>::removeAt(BinNode<T> *x)
{
    if (x == nullptr)
    {
        return;
    }

    removeAt(x->_lChild);
    removeAt(x->_rChild);

    delete x;
}

template <typename T>
void BinTree<T>::remove(BinNode<T> *x)
{
    BinNode<T> *p = x->_parent;

    if (x == _root)
    {
        _root = nullptr;
    }
    else if (x == p->_lChild)
    {
        p->_lChild = nullptr;
    }
    else
    {
        p->_rChild = nullptr;
    }
    int n = countNodes(x);
    _size -= n;

    removeAt(x);

    updateHeightAbove(p);
}

template <typename T>
int BinTree<T>::countNodes(BinNode<T> *x) const
{
    if (x == nullptr)
    {
        return 0;
    }

    return 1 + countNodes(x->_lChild) + countNodes(x->_rChild);
}

template <typename T>
void BinTree<T>::updateDepthBelow(BinNode<T> *x)
{
    if (x == nullptr)
    {
        return;
    }

    if (x->_lChild != nullptr)
    {
        x->_lChild->_depth = x->_depth + 1;
        updateDepthBelow(x->_lChild);
    }

    if (x->_rChild != nullptr)
    {
        x->_rChild->_depth = x->_depth + 1;
        updateDepthBelow(x->_rChild);
    }
}

template <typename T>
BinTree<T> *BinTree<T>::secede(BinNode<T> *x)
{
    BinNode<T> *p = x->_parent;

    BinTree<T> *S = new BinTree<T>();
    S->_root = x;
    S->_size = countNodes(x);
    x->_parent = nullptr;
    x->_depth = 0;
    updateDepthBelow(x);

    if (p->_lChild == x)
    {
        p->_lChild = nullptr;
    }
    else if (p->_rChild == x)
    {
        p->_rChild = nullptr;
    }

    _size -= S->_size;
    updateHeightAbove(p);

    return S;
}

template <typename T>
template <typename VST>
void BinTree<T>::travPreAt(BinNode<T> *x, VST &visit)
{
    if (x == nullptr)
    {
        return;
    }

    visit(x->_data);
    travPreAt(x->_lChild, visit);
    travPreAt(x->_rChild, visit);
}

template <typename T>
template <typename VST>
void BinTree<T>::travInAt(BinNode<T> *x, VST &visit)
{
    if (x == nullptr)
    {
        return;
    }

    travInAt(x->_lChild, visit);
    visit(x->_data);
    travInAt(x->_rChild, visit);
}

template <typename T>
template <typename VST>
void BinTree<T>::travPostAt(BinNode<T> *x, VST &visit)
{
    if (x == nullptr)
    {
        return;
    }

    travPostAt(x->_lChild, visit);
    travPostAt(x->_rChild, visit);
    visit(x->_data);
}