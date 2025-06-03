# 数据类型
默认显示运算结果，但在赋值语句后加分号只执行赋值操作

## 数值
双精度与单精度：double, single
符号整型与无符号整型：int8, unit8
实型与复型：real, imag

## 结构
structure

## 元胞
cell

% 注释

## format
> format 只影响输出格式不影响数据存储

|代码   |含义   |
|---|---|
|`format `  |显示小数点后4位   |
|`format long` | 小数点后15位|
|`format short e`| 5位有效数字科学计数法|
|`format long e`| 16位有效数字科学计数法|
|`format rat`|近似有理数|


```matlab

% 小数点后4位
>> format
>> pi

ans =

    3.1416

% 小数点后15位
>> format long
>> pi

ans =

   3.141592653589793

% 5位有效数字的科学计数法
>> format short e
>> pi

ans =

   3.1416e+00

% 16位有效数字的科学计数法
>> format long e
>> pi

ans =

     3.141592653589793e+00

% 近似有理数
>> format rat
>> pi

ans =

     355/113   
```

## 预定义变量
|变量名   |表示数值   |
|---|---|
| `ans ` | 缺省变量名  |
| `pi `| 圆周率|
|`eps` | 浮点运算的相对精度|
|`inf `| 正无穷|
|`NaN` | 不定值0/0|
|`realmax/realmin`|最大/最小的浮点数|
|`i,j`|虚数单位|
|`nargin,nargout`|所用函数的输入/输出变量数目|


```matlab
>> 1

ans =

     1

>> pi

ans =

    3.1416

>> eps

ans =

   2.2204e-16

>> inf

ans =

   Inf

>> NaN

ans =

   NaN

>> realmax

ans =

  1.7977e+308

>> realmin

ans =

  2.2251e-308

>> i

ans =

   0.0000 + 1.0000i

>> j

ans =

   0.0000 + 1.0000i
```

## 内存变量的管理
`whos`, `who`显示workspace中的变量名，`clear`删除workspace中的所有变量
```matlab
>> a=1,b=2

a =

     1


b =

     2

>> who

您的变量为:

a  b  

>> whos
  Name      Size            Bytes  Class     Attributes

  a         1x1                 8  double              
  b         1x1                 8  double

>> clear
>> whos
>>           
```

## 逻辑运算与关系运算
### 逻辑运算
|运算符|含义|
|---|---|
|`&`|与|
|`|`|或|
|`~`|非|
### 关系运算
| 运算符 | 含义 |
|---|---|
| `>`  | 大于  |
|`<`|小于|
|`>=`|大于等于|
|`<=`|小于等于|
|`==`|等于|
|`~=`|不等于|


## 序列
```matlab
% 从1开始到4结束每隔0.5取一个
>> 1:0.5:4

ans =

    1.0000    1.5000    2.0000    2.5000    3.0000    3.5000    4.0000

% 从1开始到2结束一共有10个等差的数
>> linspace(1,2,10)

ans =

    1.0000    1.1111    1.2222    1.3333    1.4444    1.5556    1.6667    1.7778    1.8889    2.0000

% 从10^1开始到10^2结束一共有10个等比的数
>> logspace(1,2,10)

ans =

   10.0000   12.9155   16.6810   21.5443   27.8256   35.9381   46.4159   59.9484   77.4264  100.0000
   
```

## 矩阵
matlab中的矩阵是按列存放的，也就是说你如果用序列创建矩阵，是一列一列依次填满的。
### 创建矩阵
方括号括起来表示矩阵，分号表示换行，同行元素间以空格或逗号隔开，矩阵元素可以是运算表达式
```matlab
>> mat = [1 2 3 ; 4 5 6]

mat =

     1     2     3
     4     5     6
```


### 特殊矩阵的创建
|函数   |作用   |
|---|---|
|`zeors(m,n)`   |产生$m\times n$零矩阵，方阵情况时可以省略第二个参数   |
|`zeros(size(A))`|产生与矩阵A同样大小的零矩阵|
|`eye(m,n)`|构建单位矩阵|
|`ones(m,n)`|构建全1矩阵|
|`randi([a, b], m, n)`|元素在[a, b]之间的$m\times n$随机矩阵|
```matlab
>> zeros(3,4)

ans =

     0     0     0     0
     0     0     0     0
     0     0     0     0

>> eye(3,4)

ans =

     1     0     0     0
     0     1     0     0
     0     0     1     0

>> ones(3,4)

ans =

     1     1     1     1
     1     1     1     1
     1     1     1     1

>> randi([10,50], 5 ,5)

ans =

    47    21    49    27    11
    15    32    49    47    44
    47    49    29    42    48
    35    49    42    49    37
    13    16    15    36    41

```

### 利用 M 文件或 TXT 文件建立矩阵

可以通过 `.m` 脚本文件或 `.txt` 文本文件创建较大、复杂的矩阵。这样做的好处是便于维护、复用或从外部导入数据。

#### 使用 `.m` 文件创建矩阵

1. 打开 MATLAB 自带的 **Editor** 或使用任意文本编辑器。
2. 输入如下内容（定义一个矩阵 `mymat`）：

    ```matlab
    % 文件名：mymatrix.m
    mymat = [
        1, 2, 3;
        4, 5, 6;
        7, 8, 9
    ];
    ```

3. 将文件保存为 `mymatrix.m`，并确保保存在 MATLAB 当前工作目录中。


    ```matlab
    >> mymat

    mymat =

         1     2     3
         4     5     6
         7     8     9
    ```

#### 使用 `.txt` 文件读取纯数据矩阵

适用于数据文件中只包含纯数字（不含变量名）。

1. 创建一个名为 `mymatrix.txt` 的文本文件，内容如下：

    ```
    1 2 3
    4 5 6
    7 8 9
    ```

2. 在 MATLAB 中读取该文件内容为矩阵：

    ```matlab
    mymat = load('mymatrix.txt');
    ```

    或使用更通用的函数：

    ```matlab
    mymat = readmatrix('mymatrix.txt');
    ```

### 矩阵切片
#### MATLAB 中的矩阵切片（索引）操作
矩阵的切片操作使用括号 `( , )` 表示，其中：
- 前一部分表示 **行的索引**；
- 后一部分表示 **列的索引**；
- 可以使用数字、向量、冒号 `:`、关键字 `end` 等方式指定位置。

#### 基本语法

```matlab
A(i, j)           % 取第 i 行第 j 列的元素
A(i, :)           % 取第 i 行的所有列
A(:, j)           % 取第 j 列的所有行
A(m:n, p:q)       % 取第 m 到 n 行、第 p 到 q 列的子矩阵
A([1 3], [2 4])   % 取第 1、3 行 和第 2、4 列交叉形成的子矩阵
A(end, :)         % 取最后一行的所有列
A(:, end-1:end)   % 取最后两列的所有行
```
```matlab
>> A = [1 2 3; 4 5 6; 7 8 9]

A =

     1     2     3
     4     5     6
     7     8     9

>> A(2, 3)

ans =

     6

>> A(1, :)

ans =

     1     2     3

>> A(:, 2)

ans =

     2
     5
     8

>> A(1:2, 2:3)

ans =

     2     3
     5     6

>> A([1 3], [1 3])

ans =

     1     3
     7     9

>> 

>> A(end, :)

ans =

     7     8     9

>> A(:, end-1:end)

ans =

     2     3
     5     6
     8     9

```

### 矩阵运算
数的运算是矩阵运算的特例，所以一并包含在其中。

#### 1. 基础算术运算符

| 运算符 | 含义        | 说明                         |
|--------|-------------|------------------------------|
| `+`    | 加法        | 元素逐项相加，要求维度一致  |
| `-`    | 减法        | 元素逐项相减，要求维度一致  |
| `*`    | 矩阵乘法    | 矩阵内积规则，A的列= B的行  |
| `/`    | 右除        | `A/B` ≡ `A * inv(B)`         |
| `\`    | 左除        | `A\B` ≡ `inv(A) * B`         |
| `^`    | 矩阵幂      | `A^n` 为 `n` 次矩阵乘法      |

```matlab
>> A = [1 2; 3 4], B = [5 6; 7 8]

A =

     1     2
     3     4


B =

     5     6
     7     8

>> A + B

ans =

     6     8
    10    12

>> A - B

ans =

    -4    -4
    -4    -4

>> A * B

ans =

    19    22
    43    50

>> A / B

ans =

    3.0000   -2.0000
    2.0000   -1.0000

>> A / B * B

ans =

     1     2
     3     4

>> A \ B

ans =

    -3    -4
     4     5

>> A * (A \ B)

ans =

     5     6
     7     8

>> A ^ 2

ans =

     7    10
    15    22

```

#### 2. 点运算符（逐元素操作）

| 运算符 | 含义        |
|--------|-------------|
| `.*`   | 元素乘法    |
| `./`   | 元素右除    |
| `.\`   | 元素左除    |
| `.^`   | 元素幂      |
```matlab
>> A = [1 2; 3 4], B = [5 6; 7 8]

A =

     1     2
     3     4


B =

     5     6
     7     8

>> A .* B

ans =

     5    12
    21    32

>> A ./ B

ans =

    0.2000    0.3333
    0.4286    0.5000

>> A .\ B

ans =

    5.0000    3.0000
    2.3333    2.0000

>> A .^ 2

ans =

     1     4
     9    16

```

#### 3. 常用数学函数
下述函数若作用于矩阵则是对每一元素进行的。
| 函数     | 说明             |
|----------|------------------|
| `sqrt(x)`| 平方根           |
| `pow2(x)`| 2的幂|
| `log(x)`| 自然对数|
| `log2(x)`| 2为底的对数|
| `log10(x)`| 10为底的对数|
| `exp(x)`| e为底的指数|
| `sign(x)`| 符号函数         |
| `mod(x,y)` | 余数，x为负数时是向负数的余数       |
| `rem(x,y)` | 余数，x为负数时是向正数的余数     |
| `round(x)`| 四舍五入        |
| `floor(x)`| 向下取整        |
| `ceil(x)` | 向上取整        |
| `fix(x)`  | 向 0 方向取整    |
| `conj(x)`| 复数共轭|
| `real(x)`| 复数实部|
| `imag(x)`| 复数虚部|
| `abs(x)` |模|
| `angle(x)`| 相角|
```matlab
>> sqrt([4 9])

ans =

     2     3

>> pow2([1 2 3])

ans =

     2     4     8

>> log(exp(1))

ans =

     1

>> log2(8)

ans =

     3

>> log10(100)

ans =

     2

>> exp(1)

ans =

    2.7183

>> sign([-3 0 4])

ans =

    -1     0     1

>> mod(-7, 3)

ans =

     2

>> rem(-7, 3)

ans =

    -1

>> round(3.6)

ans =

     4

>> round(3.4)

ans =

     3

>> floor(3.6)

ans =

     3

>> ceil(3.2)

ans =

     4

>> fix(-3.7)

ans =

    -3

>> fix(3.7)

ans =

     3

>> conj(1+2i)

ans =

   1.0000 - 2.0000i

>> real(1+2i)

ans =

     1

>> imag(1+2i)

ans =

     2

>> abs(3+4i)

ans =

     5

>> angle(pi/4)

ans =

     0

```

#### 4. 矩阵变换函数

| 函数        | 说明                  |
|-------------|-----------------------|
| `transpose(A)` 或 `A.'` | 非共轭转置 |
| `fliplr(A)`     | 左右翻转          |
| `flipud(A)`     | 上下翻转          |
| `flipdim(A,1)`     | 将矩阵按第一个维度进行翻转  |
| `rot90(A)`    |旋转90度 |
| `diag(A)`|对角矩阵 |
| `rref(A)`| 最简行阶梯形矩阵|
| `tril(A)`|下三角矩阵 |
| `triu(A)`|上三角矩阵 |
|`reshape(A,m,n)`|将矩阵A重新排成$m\times n$的矩阵|
```matlab
>> A = [1 2; 3 4]

A =

     1     2
     3     4

>> transpose(A)

ans =

     1     3
     2     4

>> A.'

ans =

     1     3
     2     4

>> fliplr(A)

ans =

     2     1
     4     3

>> flipud(A)

ans =

     3     4
     1     2

>> flipdim(A, 1)

ans =

     3     4
     1     2

>> flipdim(A, 2)

ans =

     2     1
     4     3

>> rot90(A)

ans =

     2     4
     1     3

>> diag(A)

ans =

     1
     4

>> rref(A)

ans =

     1     0
     0     1

>> tril(A)

ans =

     1     0
     3     4

>> triu(A)

ans =

     1     2
     0     4

>> reshape(A, 1, 4)

ans =

     1     3     2     4

```
#### 5. 矩阵运算函数

| 函数     | 含义                 |
|----------|----------------------|
| `det(A)` | 行列式               |
| `inv(A)` | 逆矩阵               |
| `rank(A)`| 矩阵秩               |
| `trace(A)`| 对角线元素之和     |
| `norm(A)`|矩阵范数|
| `cond(A)`| 矩阵条件数|
|`[V,D]=eig(A)`|矩阵的特征值分解，`V`表示特征向量，`D`表示特征值|
| `[Q,R]=qr(A)`|矩阵的QR分解|
| `[L,U]=lu(A)`|矩阵的LU分解|

```matlab
>> det([1 2; 3 4])

ans =

    -2

>> inv([1 2; 3 4])

ans =

   -2.0000    1.0000
    1.5000   -0.5000

>> rank([1 2; 2 4])

ans =

     1

>> trace([1 2; 3 4])

ans =

     5

>> norm([3 4])

ans =

     5

>> cond([1 2; 3 4])

ans =

   14.9330

>> [V,D] = eig([1 2; 3 4])

V =

   -0.8246   -0.4160
    0.5658   -0.9094


D =

   -0.3723         0
         0    5.3723

>> [Q,R] = qr([1 2; 3 4])

Q =

   -0.3162   -0.9487
   -0.9487    0.3162


R =

   -3.1623   -4.4272
         0   -0.6325

>> [L,U] = lu([1 2; 3 4])

L =

    0.3333    1.0000
    1.0000         0


U =

    3.0000    4.0000
         0    0.6667

```
#### 6.向量内积/外积
| 函数        | 主要作用 |
| `dot`     | 点积      |
| `cross`   | 叉积      |
```matlab
>> dot([1 2 3], [4 5 6])

ans =

    32

>> cross([1 2 3], [4 5 6])

ans =

    -3     6    -3

```
#### 7.其他函数
| 函数        | 主要作用    | 向量行为    | 矩阵行为（默认）   |
| --------- | ------- | ------- | ---------- |
| `min/max` | 极值      | 单值      | 每列最值       |
| `mean`    | 平均值     | 单值      | 每列均值       |
| `median`  | 中位数     | 单值      | 每列中位数      |
| `std`     | 标准差     | 单值      | 每列标准差      |
| `diff`    | 相邻差分    | 长度减1    | 每列差分       |
| `sort`    | 升序排序    | 排序向量    | 每列排序       |
| `sum`     | 求和      | 总和      | 每列求和       |
| `prod`    | 乘积      | 累乘      | 每列累乘       |
| `cumsum`  | 累加和     | 向量累加    | 每列累加       |
| `cumprod` | 累乘积     | 向量累乘    | 每列累乘       |
| `length`  | 最大维长度   | 向量长度    | 二维矩阵为max(行,列)   |
| `size`    | 维度信息    | [1,n]  | [m,n]     |
| `norm`    | 向量/矩阵范数 | L2 范数   | 谱范数（最大奇异值） |
```matlab
>> A = reshape(1:16, 4, 4)

A =

     1     5     9    13
     2     6    10    14
     3     7    11    15
     4     8    12    16

>> min(A)

ans =

     1     5     9    13

>> max(A)

ans =

     4     8    12    16

>> mean(A)

ans =

    2.5000    6.5000   10.5000   14.5000

>> median(A)

ans =

    2.5000    6.5000   10.5000   14.5000

>> std(A)

ans =

    1.2910    1.2910    1.2910    1.2910

>> diff(A)

ans =

     1     1     1     1
     1     1     1     1
     1     1     1     1

>> sort(A)

ans =

     1     5     9    13
     2     6    10    14
     3     7    11    15
     4     8    12    16

>> sum(A)

ans =

    10    26    42    58

>> prod(A)

ans =

          24        1680       11880       43680

>> cumsum(A)

ans =

     1     5     9    13
     3    11    19    27
     6    18    30    42
    10    26    42    58

>> cumprod(A)

ans =

           1           5           9          13
           2          30          90         182
           6         210         990        2730
          24        1680       11880       43680

>> length(A)

ans =

     4

>> size(A)

ans =

     4     4

>> norm(A)

ans =

   38.6227

```

## 字符串
### 创建字符串以及字符串数组
单引号将内容括起来表示一个字符串，以ASC2码存储。
```matlab
% 创建字符串
a = 'ABC'
% 创建字符串数组，不可以使用单引号，否则输出会是字符串
>> a = ["hello" "word"]

a = 

  1x2 string 数组

    "hello"    "word"

>> a = ['hello', 'word']

a =

    'helloword'

```
### 字符函数
| 函数                          | 含义                                                                 |
|-------------------------------|----------------------------------------------------------------------|
| `abs('ABC')`                  | 返回字符串中每个字符的 ASCII 码（与 `double` 等价）                 |
| `double('ABC')`               | 返回字符串中每个字符的 ASCII 码                                     |
| `char([65 66 67])`            | 将 ASCII 数字转换为对应字符，结果为 `'ABC'`                         |
| `int2str(123)`                | 将整数转换为字符串 `'123'`                                          |
| `num2str(3.14)`               | 将数值（整数或浮点数）转换为字符串 `'3.14'`                         |
| `str2num('1.23 4.56')`        | 将字符串解析为数值向量 `[1.23 4.56]`                                |
| `strcat('ab', 'cd')`          | 字符串拼接，结果为 `'abcd'`，自动去除尾部空格                      |
| `strvcat('abc', 'defg')`      | 垂直拼接字符矩阵，按最大长度补空格                                 |
| `strcmp('abc','abc')`         | 比较字符串是否完全相同，返回 `1`（true）或 `0`（false）             |
| `strncmp('abcdef','abcxyz',3)`| 比较字符串前3个字符是否相同，返回逻辑值                            |
| `strrep('cat','a','o')`       | 将字符串中的 `'a'` 替换为 `'o'`，结果为 `'cot'`                     |
| `strmatch('he', ['hello','hero','hi'])` | 返回所有以 `'he'` 开头的字符串索引                  |
|`eval()`|将字符串理解为代码执行|
```matlab
>> abs('A')

ans =

    65

>> double('A')

ans =

    65

>> char(65)

ans =

    'A'

>> int2str(123)

ans =

    '123'

>> num2str(3.14)

ans =

    '3.14'

>> str2num('1.23 4.56')

ans =

    1.2300    4.5600

>> strcat('ab', 'cd')

ans =

    'abcd'

>> strcat('ab', 'cd ')

ans =

    'abcd'

>> strvcat('abc', 'defg')

ans =

  2x4 char 数组

    'abc '
    'defg'

>> strcmp('abc', 'abc')

ans =

  logical

   1

>> strcmp('abc', 'ab')

ans =

  logical

   0

>> strncmp('abcdef', 'abcxyz', 3)

ans =

  logical

   1

>> strncmp('abcdef', 'abcxyz', 4)

ans =

  logical

   0

>> strrep('cat', 'a', 'o')

ans =

    'cot'

>> strmatch('he', 'hi')

ans =

     []

>> strmatch('he', 'he')

ans =

     1

>> strmatch('he', ["he" "him"; "s" "hem"])

ans =

     1
     4

>> strmatch('he', ["hello";"hero";"hi"])

ans =

     1
     2

>> eval("a=2")

a =

     2

```

# 程序设计

## 函数文件

在 MATLAB 中，**函数文件（Function File）** 是用于定义自定义函数的基本方式，扩展名为 `.m`。它可以接收输入参数，执行一系列操作并返回结果。

### 1.函数文件的基本结构

函数文件以 `function` 开头，其基本结构如下：

```matlab
function [输出1, 输出2, ...] = 函数名(输入1, 输入2, ...)
    % 函数说明
    % 执行语句
end
```

- **文件名必须和函数名一致**，例如函数叫 `myadd`，文件名必须是 `myadd.m`。
- 可定义多个输入和多个输出。
- 一个函数文件只能有一个主函数，可以包含多个**子函数**。

### 2.创建并使用函数文件的示例

定义一个加法函数 `myadd.m`。

```matlab
function result = myadd(a, b)
    % myadd: 返回 a + b 的结果
    % 输入检查
    if nargin ~= 2
        error('需要两个输入参数');
    end
    if ~isnumeric(a) || ~isnumeric(b)
        error('输入参数必须是数值类型');
    end
    result = a + b;
end
```

**调用方法：**

```matlab
>> r = myadd(3, 5)
r =
     8
```
需要注意**函数文件必须在当前工作路径中，否则索引不到**。


### 3.带多个输出的函数示例

定义一个计算平均值与标准差的函数 `mystat.m`。

```matlab
function [avg, s] = mystat(x)
    % mystat: 返回平均值和标准差
    if nargin ~= 1
        error('需要一个输入向量');
    end
    if ~isvector(x) || ~isnumeric(x)
        error('输入必须是数值向量');
    end

    n = length(x);
    avg = sum(x) / n;
    s = sqrt(sum((x - avg).^2) / (n - 1));
end
```

**调用方法：**

```matlab
>> [mean_val, std_val] = mystat([1 2 3 4 5])
mean_val =
     3
std_val =
     1.5811
```

---

### 4.包含子函数的函数文件

一个函数文件中可以包含多个函数，但只有**第一个函数（主函数）** 是对外可见的，其他的是子函数，仅供主函数调用。

```matlab
function y = mainfunc(x)
    y = helperfunc(x) + 1;
end

function z = helperfunc(x)
    z = x^2;
end
```

## 流程控制

### 1. `if` 条件语句

用于执行满足条件的代码块。
**语法：**

```matlab
if 条件1
    % 条件1为真时执行的语句
elseif 条件2
    % 条件2为真时执行的语句
else
    % 所有条件不满足时执行
end
```
**示例：**

```matlab
x = 5;
if x > 10
    disp('x 大于 10');
elseif x == 5
    disp('x 等于 5');
else
    disp('x 小于或等于 10 且不等于 5');
end
x 等于 5
```
### 2. `switch` 多分支选择语句

根据变量的值选择执行哪个代码块，适用于多个固定值的判断。
**语法：**
```matlab
switch 变量
    case 值1
        % 变量等于值1时执行
    case 值2
        % 变量等于值2时执行
    otherwise
        % 所有情况都不匹配时执行
end
```
**示例：**

```matlab
day = 'Monday';
switch day
    case 'Monday'
        disp('今天是星期一');
    case 'Tuesday'
        disp('今天是星期二');
    otherwise
        disp('不是星期一也不是星期二');
end
今天是星期一
```
### 3. `try-catch` 异常处理语句

用于捕捉运行时错误，使程序即使遇到异常也不会中断运行。


**语法：**

```matlab
try
    % 尝试执行的代码
catch 异常变量
    % 出错时执行的代码
end
```

**示例：**

```matlab
>> try
     result = 10 / a
   catch ME
     disp('发生错误：');
     disp(ME);
   end
发生错误：
  MException - 属性:

    identifier: 'MATLAB:UndefinedFunction'
       message: '函数或变量 'a' 无法识别。'
         cause: {}
         stack: [0x1 struct]
    Correction: []

>> 
```
#### ME与lasterr

在早期 MATLAB 版本中，catch 子句不接变量名，错误信息由内置变量 lasterr 存储。示例如下：

```matlab
>> try
    result = 10 / a;
catch
    disp('出错：');
    disp(lasterr);  % 显示最后一条错误信息
end
出错：
函数或变量 'a' 无法识别。
```
lasterr 是一个全局变量，保存最后发生的错误信息。

在新版本 MATLAB 中（R2010+），推荐使用结构化异常对象 MException 处理错误。catch 后可以接一个变量（如 ME），此变量就是一个 MException 对象。

```matlab
try
    result = 10 / 0;
catch ME
    disp('发生错误：');
    disp(ME.message);        % 错误消息字符串
    disp(ME.identifier);     % 错误标识符（如'MATLAB:divideByZero'）
    disp(ME.stack(1));       % 错误发生的位置（文件、行号、函数）
end
```
**MException 对象详解:**
当错误发生时，MATLAB 会创建一个 MException 类型的对象，常用属性如下：

|属性名|	说明|
|---|---|
|ME.message|	错误的文本描述|
|ME.identifier|	错误的唯一标识符|
|ME.stack|	一个结构数组，描述错误发生的函数、文件和行号|
|ME.cause|	若是嵌套异常或 rethrow，可追踪根本原因|


### 4. `while` 循环语句

当条件为真时反复执行某段代码。

**语法：**

```matlab
while 条件
    % 循环体
end
```

**示例：**
```matlab
i = 1;
while i <= 5
    disp(['当前 i = ', num2str(i)]);
    i = i + 1;
end
当前 i = 1
当前 i = 2
当前 i = 3
当前 i = 4
当前 i = 5
```
### 5. `for` 循环语句

用于对已知范围的变量进行迭代。

**语法：**

```matlab
for 变量 = 向量或数组
    % 循环体
end
```
**示例：**

```matlab
for i = 1:5
    disp(['i = ', num2str(i)]);
end
i = 1
i = 2
i = 3
i = 4
i = 5
```


### break和continue

| 控制语句 | 说明                     |
|----------|--------------------------|
| `break`  | 终止当前循环             |
| `continue` | 跳过当前循环的剩余部分，直接进入下一轮 |

**示例：**

```matlab
for i = 1:10
    if mod(i, 2) == 0
        continue;  % 跳过偶数
    end
    if i > 7
        break;     % 超过 7 时跳出循环
    end
    disp(i);
end
     1

     3

     5

     7
```
