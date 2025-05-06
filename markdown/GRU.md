# GRU——Gated Recurrent Unit

| 符号            | 含义                  | 矩阵大小           |
| ------------- | ------------------- | -------------- |
| $x_t$         | 当前时刻的输入信息           | $m\times1$     |
| $h_{t-1}$     | 上一时刻的隐藏状态           | $n\times1$     |
| $h_t$         | 传递到下一时刻的隐藏状态        | $n\times1$     |
| $\tilde{h}_t$ | 候选隐藏状态              | $n\times1$     |
| $z_t$         | 更新门输出               | $n\times1$     |
| $r_t$         | 重置门输出               | $n\times1$     |
| $\sigma$      | Sigmoid函数，值域$[0,1]$ |                |
| $tanh$        | tanh函数，值域$[-1,1]$   |                |
| $W_r$         | 重置门权重矩阵             | $n\times(m+n)$ |
| $W_z$         | 更新门权重矩阵             | $n\times(m+n)$ |
| $W$           | 候选隐藏状态计算矩阵          | $n\times(m+n)$ |

## 结构

### 重置门

$$
r_{ta}=\sigma(W_r\cdot[h_{t-1},x_t]^T)
$$

重置门选择了sigmoid激活函数将值映射到$[0,1]$之间，所得的$r_t$接下来对$h_{t-1}$作Hadamard乘积，决定保留多少历史信息。重置的含义也就是利用记忆的信息与现在传入的信息决定要保留多少历史信息。

### 更新门

$$
z_t=\sigma(W_z\cdot[h_{t-1},x_t]^T)
$$

更新门决定使用多少历史信息和当前信息来更新当前隐藏状态

### 候选隐藏状态

$$
\tilde{h}_t=tanh(W\cdot[r_t\odot h_{t-1},x_t]^T)
$$

利用重置门计算得到的 $r_t$ 对过去的 $h_{t-1}$ 进行遗忘，再并入现在的信息$x_t$，利用 $W$ 作映射再使用tanh激活。

### 更新隐藏状态

$$
h_t=z_t\odot h_{t-1}+(1-z_t)\odot\tilde{h}_t
$$

利用更新门计算得到的 $z_t$ 对过去的历史信息 $h_{t-1}$ 作 Hadamard 乘积，决定留下多少历史信息。再对候选隐藏状态 $\tilde{h}_t$ 作 Hadamard 乘积，决定并入多少当前信息。

### 下一层的输入

上一层每个时间步输出的 $h_t$ 将作为下一层输入的 $x_t$ 。

## $h_t$ 的初始化

每一层的 $h_0$ 都需要初始化，如果不传递参数，pytorch默认全为 $0$ 

## 参数问题

### 共享参数

<mark>GRU在不同时间步的网络参数是相同的</mark>，在每一层之间是不一样的。这使得<u>网络可以处理任意长度的序列</u>。

### 参数量

设层数为num_layers，整个GRU的参数量为：

$$
num\_layers\times3\times n\times(m+n)
$$

## 梯度消失问题的解决

1. 重置门帮助捕获序列中的短期依存关系（short-term dependencies）

2. 更新门帮助捕获序列中的长期依存关系（long-term dependencies）

## 代码

### nn.GRU简介

```python
import torch.nn as nn

rnn = nn.GRU(input_size, hidden_size, num_layers, bias, 
             batch_first, dropout, bidirectional)
```

1. input_size：特征维度 $m$

2. hidden_size：隐藏层维度 $n$ 

3. num_layers：网络层数

4. bias：线性映射时是否使用bias项，默认为T

5. batch_first：如果为F，输入维度应为`（time_step, batch, input_size）`；如果为T，输入维度应为`（batch, time_step, input_size）`；

6. dropout：隐藏层dropout率，默认为 $0$

7. bidirectional：是否使用双向的GRU，如果为T，则自动将序列正序、反序各输入一次

```python
output, h_n = gru(input, h_0)
```

1. h_0是初始化的第一个时间步的隐藏状态，维度需要为`(num_layers * num_directions, batch, hidden_size)`

2. output形状：(`time_step，batch，num_directions * hidden_size)` 。这个ouput包含了每个时间步的输出。可以使用`output.view(seq_len, batch, num_directions, hidden_size)`分解维度。

3. 隐藏层形状：`(num_layers * num_directions, batch, hidden_size)`。可以使用`h_n.view(num_layers, num_directions, batch, hidden_size)`分解维度。

### 数值型预测输出的完整代码

使用MSE作为Loss，同时将时间序列数据划分为一个一个滑动时间步输入进行训练。利用Adam优化器。

```python
import time

import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from torch.utils.tensorboard import SummaryWriter


class GRUNet(nn.Module):
    """
    A GRU model for sequence processing.

    Parameters
    ----------
    input_size : int
        The number of input features (dimension of the input data).
    hidden_size : int
        The number of features in the hidden state of the GRU.
    num_layers : int
        The number of stacked GRU layers.
    output_size : int
        The number of output features (dimension of the final output).
    bias : bool, optional, default=True
        Whether to use bias in the GRU layers.
    output_type : {'last', 'mean'}, optional, default='last'
        Determines how to process GRU outputs:
        - 'last' uses the output from the last time step.
        - 'mean' uses the average of all time steps.
    dropout : float, optional, default=0.2
        Dropout rate applied to the GRU layers to prevent overfitting.
    bidirectional : bool, optional, default=False
        Whether to use a bidirectional GRU.
    """

    def __init__(self, input_size, hidden_size, num_layers, output_size, bias=True, output_type='last', dropout=0.2, bidirectional=False):
        super(GRUNet, self).__init__()

        # Initialize the GRU layer
        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            bias=bias,
            batch_first=True,
            dropout=dropout,
            bidirectional=bidirectional
        )

        # Fully connected layer (adjusted for bidirectional GRU)
        self.fc = nn.Linear(hidden_size * (2 if bidirectional else 1), output_size)

        # Output type: 'last' for last timestep or 'mean' for the mean of all timesteps
        self.output_type = output_type

    def forward(self, x, h_0=None):
        """
        Perform a forward pass through the GRU model.

        Parameters
        ----------
        x : torch.Tensor
            Input tensor of shape (seq_len, batch_size, input_size).
        h_0 : torch.Tensor, optional
            Initial hidden state of shape (seq_len, batch_size, input_size). 
            If None, it will be initialized to zeros.

        Returns
        -------
        torch.Tensor
            The output tensor after passing through the GRU and the fully connected layer.
            The shape of the output is (batch_size, output_size).
        """

        # Pass input through the GRU layer
        out, _ = self.gru(x, h_0)

        # Process the output based on the specified output type
        if self.output_type == 'last':
            out = out[-1, :, :]  # Use the output from the last timestep
        elif self.output_type == 'mean':
            out = out.mean(dim=0)  # Compute the mean over all timesteps

        # Pass the processed output through the fully connected layer
        out = self.fc(out)
        return out


def initialize_model(config, device):
    """
    Initialize the model, loss function, and optimizer.

    Parameters
    ----------
    config : dict
        Hyperparameter dictionary containing settings such as input_size, hidden_size, etc.
    device : torch.device
        Device to run the model on ('cuda' or 'cpu').

    Returns
    -------
    model : GRUNet
        The initialized GRU model.
    criterion : nn.Module
        The loss function (Mean Squared Error in this case).
    optimizer : torch.optim.Optimizer
        The optimizer (Adam in this case).
    """
    # Initialize the GRU model
    model = GRUNet(
        input_size=config['input_size'],
        hidden_size=config['hidden_size'],
        num_layers=config['num_layers'],
        output_size=config['output_size'],
        bias=config["bias"],
        output_type=config['output_type'],
        dropout=config['dropout'],
        bidirectional=config['bidirectional']
    ).to(device)

    # Loss function and optimizer
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=config['learning_rate'])

    return model, criterion, optimizer


def train(model, train_loader, criterion, optimizer, num_epochs, device, writer):
    """
    Train the GRU model.

    Parameters
    ----------
    model : nn.Module
        The GRU model to train.
    train_loader : torch.utils.data.DataLoader
        DataLoader for training data.
    criterion : nn.Module
        The loss function.
    optimizer : torch.optim.Optimizer
        The optimizer used for training.
    num_epochs : int
        Number of epochs to train the model.
    device : torch.device
        Device to run the model on ('cuda' or 'cpu').
    writer : SummaryWriter
        TensorBoard writer to log the training process.

    Notes
    -----
    This function logs the following to TensorBoard:
    - Loss at each training step.
    - Average loss per epoch.
    - Gradients of all model parameters.
    """
    global_step = 0

    for epoch in range(num_epochs):
        model.train()
        epoch_loss = 0
        start_time = time.time()

        for _, (inputs, targets) in enumerate(train_loader):
            inputs, targets = inputs.to(device), targets.to(device)

            # Forward pass
            outputs = model(inputs)
            loss = criterion(outputs, targets)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Accumulate loss for the epoch
            epoch_loss += loss.item()

            # Log the loss for the current step
            global_step += 1
            writer.add_scalar(f'Loss/train', loss.item(), global_step)

            # Log gradients for all parameters every step
            for name, param in model.named_parameters():
                if param.grad is not None:
                    writer.add_histogram(f'Gradients/{name}', param.grad, global_step)

        # Log the average loss for the epoch
        avg_epoch_loss = epoch_loss / len(train_loader)
        writer.add_scalar(f'Loss/epoch', avg_epoch_loss, epoch)

        # Print results for the epoch
        print(f"Epoch [{epoch + 1}/{num_epochs}], Loss: {avg_epoch_loss:.4f}, Time: {time.time() - start_time:.2f}s")

        # Log the gradients of parameters after the epoch
        for name, param in model.named_parameters():
            if param.grad is not None:
                writer.add_histogram(f'Gradients/{name}_epoch', param.grad, epoch)

def load_data(file_name, seq_len, step_size):
    """
    Load and process data for time series prediction using a sliding window.

    Parameters:
    -----------
    file_name (str): Path to CSV file.
    seq_len (int): Length of the sliding window.
    step_size (int): Step size for sliding window (how much to move per step).

    Returns:
    --------
    tuple: (X, y) where:
        - X is the input data
        - y is the target data
    """
    data = pd.read_csv(file_name)
    # Assume the last column is the target
    X = data.iloc[:, :-1].values
    y = data.iloc[:, -1].values

    X_windowed, y_windowed = [], []

    # Create windows for training
    for i in range(0, len(X) - seq_len, step_size):
        X_windowed.append(X[i:i + seq_len])
        y_windowed.append(y[i + seq_len])  # Predict the next time step

    # If there are remaining samples that couldn't form a full window, add them as well
    if len(X) % step_size != 0:
        # Last incomplete sequence
        X_windowed.append(X[-seq_len:-1])
        y_windowed.append(y[-1])  # Use the last available target

    X = torch.tensor(X_windowed, dtype=torch.float32)
    y = torch.tensor(y_windowed, dtype=torch.float32)
    return X, y

def save_model(model, model_filename):
    """
    Save the trained model to a specified file.

    Parameters:
    -----------
    model (nn.Module): The trained PyTorch model.
    model_filename (str): The file path where the model will be saved.

    Returns:
    --------
    None
    """
    torch.save(model.state_dict(), model_filename)
    print(f"Model saved to {model_filename}")

def main():
    """
    Main function to train and evaluate the GRU model.
    """
    # Set device (GPU or CPU)
    device = torch.device(config['device'] if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load data
    file_name = config['data_file']
    seq_len = config['time_step']
    step_size = config['step_size']
    X, y = load_data(file_name, seq_len, step_size)
    train_dataset = TensorDataset(X, y)
    train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], shuffle=True)

    # Initialize model, criterion, and optimizer
    model, criterion, optimizer = initialize_model(config, device)

    # TensorBoard writer
    writer = SummaryWriter(config['log_dir'])

    # Train the model
    train(model, train_loader, criterion, optimizer, config['num_epochs'], device, writer)

    # Savzae the trained model with a defined filename
    model_filename = config['model_filename']
    save_model(model, model_filename)

    # Close the TensorBoard writer
    writer.close()

if __name__ == "__main__":
    # Configuration file for training the GRU model

    config = {
        # Data parameters
        'data_file': 'data.csv',            # Path to the CSV file containing input features and targets
        'time_step': 5,                     # Length of the sliding window (sequence length). Defines the number of time steps to consider for each input sequence.
        'step_size': 1,                     # Step size for sliding window. Defines how much to move the window for each new sequence.

        # Model parameters
        'input_size': 10,                   # Number of input features (dimension of the input data)
        'hidden_size': 64,                  # Number of features in the hidden state of the GRU
        'num_layers': 2,                    # Number of stacked GRU layers
        'output_size': 1,                   # Number of output features (dimension of the final output)
        'bias': True,                       # Whether to use bias in GRU layers
        'output_type': 'last',              # 'last' or 'mean', how to process GRU outputs
        'dropout': 0.2,                     # Dropout rate applied to GRU layers
        'bidirectional': False,             # Whether to use bidirectional GRU

        # Training parameters
        'learning_rate': 0.001,             # Learning rate for the optimizer
        'batch_size': 64,                   # Batch size for training
        'num_epochs': 20,                   # Number of epochs to train the model

        # TensorBoard parameters
        'log_dir': 'runs/gru_experiment',   # Directory to save TensorBoard logs

        # Model saving parameters
        'model_filename': 'gru_model.pth',  # Path to save the trained model

        # Device configuration (GPU or CPU)
        'device': 'cuda',                   # Device to run the model on ('cuda' or 'cpu')
    }

    main()
```
