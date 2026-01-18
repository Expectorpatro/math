# Gaussian Mixed Model

## 应用

1. 聚类
   
   K-means无法处理两个聚类中心点相同的类。比如$A\sim N(\mu,\;\sigma_1^2),\;B\sim N(\mu,\sigma_2^2)$ 是无法用k-means进行聚类的。

2. 密度估计

3. 新数据的生成

## 原理

我们认为数据空间是由某些高斯分布生成的，但对于某一具体的样本单元，我们只能观测到它的数值，而无法观测到它具体是由哪个高斯分布生成的，所以我们对样本单元背后的高斯分布进行建模的时候，认为样本单元以一定的权重（也可以理解为概率）服从某个具体的高斯分布。

## 符号说明

| 符号                                                                                                    |                                                    | 解释                                              |
| ------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------- |
| $n$                                                                                                     |                                                    | 高斯分布的个数（总体聚类的类个数）                |
| $N$                                                                                                     |                                                    | 样本数                                            |
| $x_i$                                                                                                   | $i=1,2,\dots,N$                                    | 第$i$个样本单元                                   |
| $z_i$                                                                                                   | $i=1,2,\dots,N$                                    | 第$i$个样本单元的隐变量                           |
| $c_j$                                                                                                   | $j=1,2,\dots,n$                                    | $z_i$可能的取值                                   |
| $\pi_{ij}$                                                                                              | $i=1,2,\dots,N\\j=1,2,\dots,n$                     | $p(z_i=c_j)$                                      |
| $\pi_{ij}^{(t)}$                                                                                        | $i=1,2,\dots,N,\\j=1,2,\dots,n,\\t\in\mathbb{N}^+$ | 隐变量$z_i$在第$t$步时取值为$c_j$的先验概率       |
| $\gamma_t(z_i=c_j)$                                                                                     | $i=1,2,\dots,N,\\j=1,2,\dots,n,\\t\in\mathbb{N}^+$ | 隐变量$z_i$在第$t$步时取值为$c_j$的后验概率       |
| $\pi_i=(\pi_{i1},\pi_{i2},\dots,\pi_{in})$                                                              | $i=1,2,\dots,N$                                    | $z_i$的分布                                       |
| $\mu_j$                                                                                                 | $j=1,2,\dots,n$                                    | 第$j$个高斯分布的均值                             |
| $\mu_j^{(t)}$                                                                                           | $j=1,2,\dots,n\\t\in\mathbb{N}^+$                  | 第$t$步时，第$j$个高斯分布的均值                  |
| $\mu=(\mu_1,\mu_2,\dots,\mu_n)$                                                                         |                                                    | 所有高斯分布的均值                                |
| $\Sigma_j$                                                                                              | $j=1,2,\dots,n$                                    | 第$j$个高斯分布的协方差矩阵                       |
| $\Sigma_j^{(t)}$                                                                                        | $j=1,2,\dots,n\\t\in\mathbb{N}^+$                  | 第$t$步时，第$j$个高斯分布的协方差矩阵            |
| $\Sigma=(\Sigma_1,\Sigma_2,\dots,\Sigma_n)$                                                             |                                                    | 所有高斯分布的协方差矩阵                          |
| $\mathbf{\theta_{i}}=(\mu_i,\;\Sigma_i)$                                                                | $i=1,2,\dots,n$                                    | 第$i$个高斯分布参数的值                           |
| $\mathbf{\theta_{i}^{(t)}}=(\mu_i^{(t)},\;\Sigma_i^{(t)})$                                              | $i=1,2,\dots,n,\\t\in\mathbb{N}^+$                 | 第$t$步时，第$i$个高斯分布参数的值                |
| $\mathbf{\theta}=(\mathbf{\theta_1},\mathbf{\theta_2},\dots,\mathbf{\theta_n})$                         |                                                    | 所有高斯分布参数的值                              |
| $\mathbf{\theta^{(t)}}=(\mathbf{\theta_1^{(t)}},\mathbf{\theta_2^{(t)}},\dots,\mathbf{\theta_n^{(t)}})$ |                                                    | 第$t$步时，所有高斯分布参数的值                   |
| $l(\mathbf{\theta})$                                                                                    |                                                    | 似然函数的下界函数                                |
| $l_t(\mathbf{\theta})$                                                                                  |                                                    | 似然函数的下界函数在$\mathbf{\theta^{(t)}}$下的值 |

## 隐变量（latent variable）

个体到底怎样服从于这$n$个正态分布呢？我们引入隐变量$z$来表示这一点。每一个个体的背后都有一个$z$，$z$的每一个取值都对应着一个高斯分布，$p(z_i=c_j),\;i=1,2,\dots,n$即表示第$i$个样本服从第$j$个正态分布的概率，也即第$j$个高斯分布对于第$i$个样本的权重。

| $z_i$        | $c_1$      | $c_2$      | $\cdots$ | $c_n$      |
| ------------ | ---------- | ---------- | -------- | ---------- |
| $p(z_i=c_j)$ | $\pi_{i1}$ | $\pi_{i2}$ | $\cdots$ | $\pi_{in}$ |

其中：

$$
\sum_{j=1}^n\pi_{ij}=1,\;\forall\;i=1,2,\dots,N
$$

## 算法具体过程

我们使用EM算法来求得参数$\mathbf{\theta}$。

### 似然函数的构建

给定一个数据集，假设样本间相互独立，则可以给出如下似然函数：

$$
\begin{align*}
    \log L(\mathbf{\theta})
    &=\sum_{i=1}^N\log p(x_i|\mathbf{\theta}) \\
    &=\sum_{i=1}^N\log \left(\sum_{j=1}^np(x_i,z_i=c_j|\mathbf{\theta})\right)
\end{align*}
$$

### step1

定义高斯分布个数$n$，对每个高斯分布设置初始参数值$\mathbf{\theta_i^{(0)}}=(\mu_i^{(0)},\;\Sigma_i^{(0)}),\;i=1,2,\dots,n$，并对所有$\pi_{ij}$设置初始参数值$\pi_{ij}^{(0)}$。一般通过k-means算法计算初始值，即先使用k-means聚出$n$类，对每一类计算它们的均值和协方差矩阵作为初始值。

### step2 E-step

因为对数函数是个凹函数，由Jensen不等式的期望形式（可见([Jensen's inequality - Wikipedia](https://en.wikipedia.org/wiki/Jensen%27s_inequality))），将$\frac{p(x_i,z_i|\mathbf{\theta})}{\pi_{ij}}$看作为$g(z_i)$，$\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\pi_{ij}}$即为$g(z_i=c_j)$，$\pi_{ij}$看作为$p(g(z_i=c_j))$，就有：

$$
\begin{align*}
    \log L(\mathbf{\theta})
    &=\sum_{i=1}^N\log \sum_{j=1}^np(x_i,z_i=c_j|\mathbf{\theta}) \\
    &=\sum_{i=1}^N\log \sum_{j=1}^n\pi_{ij}\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\pi_{ij}} \\
    &=\sum_{i=1}^N\log E[g(z_i)] \\
    &\geqslant\sum_{i=1}^N E[\log g(z_i)] \\
    &=\sum_{i=1}^N\sum_{j=1}^n\pi_{ij}\log\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\pi_{ij}}
\end{align*}
$$

因此我们可以通过提高$\sum_{i=1}^N\sum_{j=1}^n\pi_{ij}\log\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\pi_{ij}}$ 的下界来提高似然函数值。由Jensen不等式等号成立的条件，当$g(z_i)=E[g(z_i)]$时等号成立。令$E[g(z_i)]=C$，于是此时：

$$
\begin{gather*}
    \frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\pi_{ij}}=C,\;\forall\;j\in\{1,2,\dots,n\} \\
    \sum_{j=1}^np(x_i,z_i=c_j|\mathbf{\theta})=\sum_{j=1}^nC\pi_{ij} \\
    \sum_{j=1}^np(x_i,z_i=c_j|\mathbf{\theta})=C
\end{gather*}
$$

也即：

$$
\begin{align*}
    \pi_{ij}
    &=\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\sum_{k=1}^np(x_i,z_i=c_k|\mathbf{\theta})} \\
    &=\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{p(x_i|\mathbf{\theta})} \\
    &=p(z_i=c_j|x_i,\mathbf{\theta})
\end{align*}
$$

这说明在固定高斯分布参数的时候，使似然函数下界达到最大值的$\pi_{ij}$的计算公式即为$z_i=c_j$的后验概率。

根据当前参数$\mathbf{\theta^{(t)}}=(\mathbf{\theta_1^{(t)}},\mathbf{\theta_2^{(t)}},\dots,\mathbf{\theta_n^{(t)}})$和$\pi_{ij}^{(t)},\;i=1,2,\dots,N,\;j=1,2,\dots,n$，计算每一个隐变量的后验概率分布：

$$
\gamma_t(z_i=c_j)=\frac{\pi_{ij}^{(t)}N(x_i|\mu_j^{(t)},\Sigma_j^{(t)})}{\sum\limits_{k=1}^n\pi_{ik}^{(t)}N(x_i|\mu_k^{(t)},\Sigma_k^{(t)})}
$$

令$\pi_{ij}^{(t+1)}=\gamma_t(z_i=c_j)$。

### step3 M-step

我们在前面使用隐变量的后验概率分布提高了似然函数能达到的理论下界，接下来的工作就是优化参数$\mathbf{\theta}$来提高现在似然函数实际下界的值，那么我们就提高了似然函数的值。也即：

$$
\begin{align*}
    \mathbf{\theta^{(t+1)}}
    &=\argmax_\mathbf{\theta^{(t+1)}} l(\mathbf{\theta}) \\
    &=\argmax_\mathbf{\theta^{(t+1)}}\sum_{i=1}^{N}\sum_{j=1}^n\pi_{ij}\log\frac{p(x_i,z_i=c_j|\mathbf{\theta})}{\pi_{ij}} \\
    &=\argmax_\mathbf{\theta^{(t+1)}}\sum_{i=1}^N\sum_{j=1}^n\pi_{ij}\log\frac{N(x_i|\mu_j,\Sigma_j)}{\pi_{ij}}
\end{align*}
$$

对于这个优化问题，我们就可以使用一般的极大似然估计（MLE）去做了。

对$l(\mathbf{\theta})$中的各参数求偏导，令偏导为$0$，即可求得$\mathbf{\theta}$的更新公式为：

$$
\begin{align*}
    \mu_j^{(t+1)}&=\frac{\sum_{i=1}^N\pi_{ij}^{(t+1)}x_i}{\sum_{i=1}^N\pi_{ij}^{(t+1)}} \\
    \Sigma_j^{(t+1)}&=\frac{\sum_{i=1}^N\pi_{ij}^{(t+1)}(x_i-\mu_j^{(t)})(x_i-\mu_j^{(t)})^T}{\sum_{i=1}^N\pi_{ij}^{(t+1)}}
\end{align*}
$$

### step4 重复E-step和M-step直到收敛

由于似然函数值有上界$1$，而EM算法会不断提高似然函数值，所以算法最终会收敛。但是要注意，迭代一定会收敛，但不一定会收敛到真实的参数值，因为可能会陷入局部最优。所以 EM 算法的结果很受初始值的影响。

可设置$\varepsilon$，当$|l_{t+1}(\mathbf{\theta})-l_{t}(\mathbf{\theta})|<\varepsilon$时，认为已经达到收敛，停止训练。

### 超参数$n$的选择

使用AIC与BIC去选择合适的$n$。

## 代码实现

这里使用sklearn中的函数进行建模。

```python
from sklean.mixture import GaussianMixture

GaussianMixture(n_components=1, *, covariance_type='full', tol=0.001, reg_covar=1e-06, max_iter=100, n_init=1, init_params='kmeans', weights_init=None, means_init=None, precisions_init=None, random_state=None, warm_start=False, verbose=0, verbose_interval=10)[source]
```

具体参数解释与使用请参考sklearn官网文档。[GaussianMixture &#8212; scikit-learn 1.6.0 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html)

## 结果

我们最终得到了三组参数，分别为$\pi=(\pi_1,\pi_2,\dots,\pi_N),\;\mu=(\mu_1,\mu_2,\dots,\mu_n),\;\Sigma=(\Sigma_1,\Sigma_2,\dots,\Sigma_n)$

1. 目的是聚类
   
   对于每一个样本单元产生了一个$\pi_i=(\pi_{i1},\pi_{i2},\dots,\pi_{in})$，即样本单元以怎样的概率服从$n$个具体的高斯分布，取$j=\argmax_j\pi_{ij}$，可认为该样本单元属于第$j$个高斯分布,也即第$j$类。

## GMM优缺点

1. 优点：
   
   - GMM聚出的类可以呈现出椭圆形，优于k-means的圆形
   
   - GMM得到的最终结果是样本属于每一类的概率，而不像k-means那样必须把样本分给某一类。

2. 缺点：
   
   - 对大规模数据和多维高斯分布，计算量大，迭代速度慢
   
   - 如果初始值设置不当，收敛过程的计算代价会非常大。
   
   - EM算法求得的是局部最优解而不一定是全局最优解。

# References

[【机器学习笔记11】高斯混合模型（GMM）【上篇】原理与推导_高斯混合模型推导-CSDN博客](https://blog.csdn.net/qq_52466006/article/details/127186276)

[【机器学习】EM——期望最大（非常详细）](https://zhuanlan.zhihu.com/p/78311644)

[高斯混合模型（GMM）](https://zhuanlan.zhihu.com/p/30483076)
