```python
import torch.multiprocessing as mp

# 使用三块 GPU
world_size = 3
# 指定要使用的 GPU 编号
gpus = [0, 1, 2]  
os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, gpus))

# 启动多个进程，每个进程执行 train 函数
mp.spawn(train, args=(world_size, parameter, train_set, val_set, test_set), nprocs=world_size, join=True)  
```

```python
def train(rank, world_size, parameter, train_set, val_set, test_set):
    # 初始化分布式进程组并设置日志
    logger, writer = setup(rank, world_size)  

    # 建立dataloader
    train_data_loader = data_prepare(train_set, parameter['batch_size'], parameter['static_embedding_path'],
                                     parameter['pad_token'], parameter['ignore_idx'], num_replicas=world_size, rank=rank)
    val_data_loader = data_prepare(val_set, parameter['batch_size'], parameter['static_embedding_path'],
                                   parameter['pad_token'], parameter['ignore_idx'], num_replicas=world_size, rank=rank)

    model = BertForMaskedLM(parameter).to(rank)
    model = DDP(model, device_ids=[rank])

    last_epoch = -1
    step = 0

    # 建立优化器
    optimizer = AdamW([{"params": model.parameters(), "initial_lr": parameter['learning_rate']}])
    scheduler = get_polynomial_decay_schedule_with_warmup(optimizer,
                                                          parameter['num_warmup_steps'], parameter['num_train_steps'],
                                                          last_epoch=last_epoch)
    # 记录最优模型
    max_acc = 0
    state_dict = None
    # 早停机制
    early_stop_counter = 0
    early_stop_patience = parameter.get('early_stop_patience', 5)
    min_delta = parameter.get('min_delta', 1e-4)
    # 初始化混合精度
    scaler = GradScaler()
    # 开始训练
    for epoch in range(parameter['epochs']):
        start_time = time.time()
        losses = 0
        for idx, (_pad, _embed, _mlm_label) in enumerate(train_data_loader):
            step += 1
            _pad = _pad.to(rank)
            _embed = _embed.to(rank)
            _mlm_label = _mlm_label.to(rank)

            with autocast():
                loss, mlm_logits = model(input_vec=_embed.permute(1, 0, 2),
                                        attention_mask=_pad,
                                        masked_labels=_mlm_label.permute(1, 0))
            del _pad, _embed
            torch.cuda.empty_cache()

            losses += loss.item()
            loss = loss / parameter['accumulate_step']  
            scaler.scale(loss).backward()

            # 每累计到一定步数就更新权重
            if (idx+1) % parameter['accumulate_step'] == 0:
                mlm_acc, _, _ = accuracy(mlm_logits, _mlm_label, parameter['ignore_idx'])
                del _mlm_label, mlm_logits
                torch.cuda.empty_cache()
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                logger.info(f"Epoch: [{epoch + 1}/{parameter['epochs']}], Batch[{idx}/{len(train_data_loader)}], "
                             f"Train loss :{loss.item()*parameter['accumulate_step']:.3f}, Train mlm acc: {mlm_acc:.3f}")
                writer.add_scalar('Training/Loss',
                                  loss.item()*parameter['accumulate_step'], scheduler.last_epoch)
                writer.add_scalar('Training/Learning Rate',
                                  scheduler.get_last_lr()[0], scheduler.last_epoch)
                writer.add_scalar('Training/Accuracy',
                                  mlm_acc, scheduler.last_epoch)
                for name, param in model.named_parameters():
                    writer.add_histogram(name, param, scheduler.last_epoch)
                    if param.grad is not None:
                        writer.add_histogram(name + '/grad', param.grad, scheduler.last_epoch)
                optimizer.zero_grad()

        # 处理epoch结束时的剩余梯度
        if len(train_data_loader) % parameter['accumulate_step'] != 0:
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            optimizer.zero_grad()
        end_time = time.time()
        train_loss = losses / len(train_data_loader)
        logger.info(f"Epoch: [{epoch + 1}/{parameter['epochs']}], Train loss: "
                     f"{train_loss:.3f}, Epoch time = {(end_time - start_time):.3f}s")

        # 验证集验证
        if (epoch + 1) % parameter['model_val_per_epoch'] == 0:
            mlm_acc, corrects, total = evaluate(val_data_loader, model, parameter['ignore_idx'], rank)
            logger.info(f"Validating accuracy: {mlm_acc:.3f}, Total: {total}, Corrects: {corrects}")
            writer.add_scalar('Validating/Accuracy', mlm_acc, scheduler.last_epoch)
            if mlm_acc - max_acc > min_delta:
                max_acc = mlm_acc
                state_dict = deepcopy(model.state_dict())
                torch.save({'current_epoch': epoch,
                            'last_epoch': scheduler.last_epoch, 
                            'step': step,
                            'max_acc': max_acc,
                            'train_loss': train_loss,
                            'config': parameter,
                            'model_state_dict': state_dict,
                            'optimizer_state_dict': optimizer.state_dict(),
                            'scheduler_state_dict': scheduler.state_dict(),},
                           parameter['model_save_path'])
                early_stop_counter = 0
            else:
                early_stop_counter += 1

            if early_stop_counter >= early_stop_patience:
                logger.info(f"Early stopping at epoch {epoch + 1}")
                break
        writer.close()

    # 加载最佳模型参数并在测试集上评估
    checkpoint = torch.load(parameter['model_save_path'], map_location=torch.device(rank))
    model.load_state_dict(checkpoint['model_state_dict'])
    test_data_loader = data_prepare(test_set, parameter['batch_size'], parameter['static_embedding_path'],
                                   parameter['pad_token'], parameter['ignore_idx'], num_replicas=world_size, rank=rank)
    test_acc, test_correct, test_total = evaluate(test_data_loader, model, parameter['ignore_idx'], rank)
    logger.info(f"Best Test Accuracy: {test_acc:.3f}, Test Total: {test_total}, Test correct: {test_correct}")
```

```python
def setup(rank, world_size):
    os.environ['MASTER_ADDR'] = 'localhost'
    os.environ['MASTER_PORT'] = '12355'
    dist.init_process_group("nccl", rank=rank, world_size=world_size)
    torch.cuda.set_device(rank)

    # 设置日志
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f'BERT_rank_{rank}.log')
    # 获取 logger 对象
    logger = logging.getLogger(f"Process_{rank}")
    logger.setLevel(logging.INFO)
    # 创建文件处理程序
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(process)d - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    # 创建控制台处理程序
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(process)d - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 设置 TensorBoard 日志目录
    log_dir = f"board_logs/process_{rank}/" + "{0:%Y-%m-%dT%H-%M-%S/}".format(datetime.now())
    os.makedirs(log_dir, exist_ok=True)
    writer = SummaryWriter(log_dir=log_dir)
    return logger, writer
```
