# 决策树算法

## 信息论

### 信息量

我们想要找一个函数$I(x)$来对事件产生的信息量进行定量的分析，其中$x$代表着一个事件。显然信息量具有如下两个性质：

1. **一件事发生的概率越小，那么这件事发生后产生的信息量越大。** 

2. **如果两件事情独立，那么这两件事情都发生所产生的信息量应该等于每件事情各自发生产生的信息量之和。**

**由(1)，$I(x)$需要与$x$发生的概率呈反比；由(2)，$I(x)$应具有对数的形式，** 因为如果取$f(x)=\log\Big(\mathrm{Pr}(x)\Big)$，将$x,y$两个互相独立的事件同时发生的概率记为$\mathrm{Pr}(x,y)$、产生的信息量记为$f(x,y)$，那么：

$$
\begin{align*}
f(x,y)&=\log\Big(\mathrm{Pr}(x,y)\Big)=\log\Big(\mathrm{Pr}(x)\mathrm{Pr}(y)\Big) \\
&=\log\Big(\mathrm{Pr}(x)\Big)+\log\Big(\mathrm{Pr}(y)\Big) \\
&=f(x)+f(y)
\end{align*}

$$

综合考虑以上两点，我们**将一件事情发生所产生的信息量定义为它发生概率倒数的对数**，即：

$$
I(x)=-\log_2[\mathrm{Pr}(x)]
$$

**对数底的选择是任意的，但在信息论中普遍使用$2$作为对数的底。**

### 信息熵

**信息熵是某个随机变量可能产生的信息量的期望**，它同样**表征了不确定性的大小**（思考是为什么）。 设$X$是一个离散型随机变量，有$n$个取值，分别为$x_1,x_2,\dots,x_n$，则$X$的信息熵$H(X)$为：

$$
\begin{align*}
H(X)&=E[I(X)]=E\left[-\log_2\Big(\mathrm{Pr}(X)\Big)\right] \\
&=-\sum_{i=1}^n\mathrm{Pr}(X=x_i)\log_2[\mathrm{Pr}(X=x_i)]
\end{align*}
$$

称由样本计算得到的熵为**经验熵**。

#### 条件熵

**条件熵是给定一定条件下某个随机变量的信息熵**。设$X,Y$是两个离散型随机变量，分别有$n$个和$m$个取值，分别为$x_1,x_2,\dots,x_n$和$y_1,y_2,\dots,y_m$，则$X$在$Y$下的条件熵$H(X|Y)$为：

$$
\begin{align*}
H(X|Y)&=E[I(X|Y)]=E\left[\sum_{i=1}^m\mathrm{Pr}(Y=y_i)I(X|Y=y_i)\right] \\
&=\sum_{i=1}^m\mathrm{Pr}(Y=y_i)E\left[I(X|Y=y_i)\right] \\
&=\sum_{i=1}^m\mathrm{Pr}(Y=y_i)E\left[-\log_2\Big(\mathrm{Pr}(X|Y=y_i)\Big)\right] \\
&=-\sum_{i=1}^m\mathrm{Pr}(Y=y_i)\sum_{j=1}^n\mathrm{Pr}(X=x_j|Y=y_i)\log_2\Big[\mathrm{Pr}(X=x_j|Y=y_i)\Big]
\end{align*}
$$

$X$在$Y=y_i$下的条件熵$H(X|Y=y_i)$为：

$$
\begin{align*}
H(X|Y=y_i)&=E[I(X|Y=y_i)] \\
&=E\left[-\log_2\Big(\mathrm{Pr}(X|Y=y_i)\Big)\right] \\
&=-\sum_{j=1}^n\mathrm{Pr}(X=x_j|Y=y_i)\log_2\Big[\mathrm{Pr}(X=x_j|Y=y_i)\Big]
\end{align*}
$$

## 决策树

决策树算法的思路非常简单，很类似于我们日常作决策的一连串行为。写到这里的时候是星期四，就以疯狂星期四举例，假设我现在想吃KFC了，那我能不能去吃呢？第一个问题就是我有没有钱，如果有钱，那我接下来需要考虑是否有时间；如果没钱，那在去不去紫金商业街KFC这件事的决策上，我只能选择不去。如果有钱有时间，那我可以去；如果有钱没时间，那我还是去不了。决策树的执行就是这样一步一步做判断的过程。

![](C:\Users\Expector\AppData\Roaming\marktext\images\2025-03-26-17-13-46-image.png)

我们称每一个判断条件发生的地方为**内部节点**，如上图中的$\,\mathrm{age}<15$；称判断结果的指向线条为**边**，如上图中标有Y或N的线条；称最终归类样本得出结论的地方为**叶节点**，如上图中的Leaf1。**一个决策树，就是一个由内部节点、边和叶节点构成的结构**。

我们使用决策树干什么呢？用它来做分类任务或者回归任务。

![](C:\Users\Expector\AppData\Roaming\marktext\images\2025-03-26-17-24-47-image.png)

上面有一些样本，是一些西瓜的特征，有的瓜是好瓜，有的瓜是坏瓜，我希望通过这组数据来学习到好瓜的通用特征，也就是什么样的瓜会是一个好瓜，这是一个典型的分类任务。回归的话那么就是把“好瓜”这一列换成一个需要去预测的连续型变量。分类寻找各标签会在什么样的情况下出现，回归则是找在什么样的情况下更容易出现这样的数值，二者本质其实是一样的，都是去总结特征而已。

如何去总结每个类别的特征呢？

我们按照一定的顺序去选择特征，每个特征都有几种取值，依次来产生树状的决策路径，我们最终希望的是：生成的决策树在样本集上效果很好，即我希望生成的每个叶节点被分到的样本它们的类别尽量都是一样的（回归时则希望数值相近）；它也得具有一定的泛化性能。

由此我们想到了条件熵，如果$H(X)$较大但是条件熵$H(X|Y)$小，那么这就说明知道$Y$这个变量之后$X$的不确定性会下降很多。用西瓜的例子来讲，如果什么信息也没有，你给我一个西瓜，我当然很难判断它是不是一个好瓜，但如果存在某个特征或某个特征的组合，具有这些特征的瓜很大概率是好瓜或者坏瓜，那么这就很好了，这样的特征或者特征组合就是我们想要寻找的$Y$。这样一来怎么找特征也一目了然了，计算标签的信息熵，再对每个特征去计算它们为标签带来的条件熵，即寻找：

$$
\argmax_{Y}H(X)-H(X|Y)
$$

选中的$Y$即为分枝的变量，设$Y$有$m$个取值$y_1,y_2,\dots,y_m$，则接下来会产生$m$条边。每条边的末端又会产生一个新的内部节点，接下来再重复之前的过程去寻找这个新结点我们应该选择哪个特征来进行分枝。

接下来我们来详细讨论：

1. 如何选择分枝特征

2. 连续型变量该如何处理

3. 分枝分到何时结束

4. 样本信息不全，存在缺失值该如何处理

### 如何选择分枝特征

#### 信息增益

信息增益的定义式如下：

$$
\mathrm{Gain}=H(X)-H(X|Y)
$$

它表示在有了变量$Y$的信息之后$X$的不确定性的减少量。

设目标变量为$Y$，样本集为$\mathcal{D}$，特征名构成的集合为$\mathcal{F}$，

下给出使用信息增益准则选择特征的算法：

### 不再分枝的情况

我们进行判断，对样本进行不断地分类

1. 在CART中，如果既出现分类变量又出现连续型变量，如何选取划分变量，对于分类变量计算Gini系数，但对于连续型变量是计算方差和，二者无法比较。

2. CART使用二叉树结构，对于连续型变量很好处理，但若对于类别数目大于2的分类变量而言，如何计算混合取值的Gini系数？

3. 如何处理缺失值？如何进行基于损失函数的剪枝？

$$
\begin{align*}
Gain&=H(Y)-H(Y|A_i) \\
&=H(Y)-\sum_{j=1}^{|A_i|}
\end{align*}
$$

```python
import numpy as np
import pandas as pd
from collections import Counter

def entropy(y):
    counts = np.bincount(y)
    probabilities = counts / len(y)
    return -np.sum([p * np.log2(p) for p in probabilities if p > 0])

def information_gain(feature, y):
    total_entropy = entropy(y)
    values, counts = np.unique(feature, return_counts=True)

    weighted_entropy = sum((counts[i] / sum(counts)) * 
                           entropy(data[data[feature] == values[i]][target].values) 
                           for i in range(len(values)))
    return total_entropy - weighted_entropy

def gain_ratio(data, feature, target):
    ig = information_gain(data, feature, target)
    values, counts = np.unique(data[feature], return_counts=True)
    split_info = -np.sum((counts / sum(counts)) * np.log2(counts / sum(counts)))
    return ig / split_info if split_info != 0 else 0

def gini_index(data, feature, target):
    values, counts = np.unique(data[feature], return_counts=True)
    gini = 0
    for v in values:
        subset = data[data[feature] == v][target]
        subset_counts = np.bincount(subset)
        subset_prob = subset_counts / subset_counts.sum()
        gini += (counts[values == v] / sum(counts)) * (1 - np.sum(subset_prob ** 2))
    return gini
```

“这个自我意识把它自己的人格外化出来，从而把它的世界创造出来，并且把它创造的世界当作一个异己的世界看待，因此，它现在必须去加以占有。但是，去否定它的自为存在即是去创造现实，并且通过这种否定与创造，自我意识也就直接占有了现实。--或者换另一个说法，自我意识只有当它异化其自身时，才是一种什么东西，才有实在性: 通过他的自我异化，它就使自己成为普遍性的东西，而它的这个普遍性即是它的效准和现实性。”--《精神现象学》黑格尔
