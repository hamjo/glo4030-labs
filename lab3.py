import torch
import torch.nn as nn
import time

from sklearn.metrics import accuracy_score
from torch.utils.data.sampler import SequentialSampler

from deeplib.history import History
from deeplib.datasets import train_valid_loaders, load_cifar10

from torch.autograd import Variable
from torchvision.transforms import ToTensor

from deeplib.net import CifarNet


def validate(model, val_loader, use_gpu=True):
    true = []
    pred = []
    val_loss = []

    criterion = nn.CrossEntropyLoss()
    model.eval()

    for j, batch in enumerate(val_loader):

        inputs, targets = batch
        if use_gpu:
            inputs = inputs.cuda()
            targets = targets.cuda()

        inputs = Variable(inputs, volatile=True)
        targets = Variable(targets, volatile=True)
        output = model(inputs)

        predictions = output.max(dim=1)[1]

        val_loss.append(criterion(output, targets).data[0])
        true.extend(targets.data.cpu().numpy().tolist())
        pred.extend(predictions.data.cpu().numpy().tolist())

    return accuracy_score(true, pred) * 100, sum(val_loss) / len(val_loss)


def validate_ranking(model, val_loader, use_gpu=True):

    good = []
    errors = []

    criterion = torch.nn.Softmax(dim=1)
    model.eval()

    for batch in val_loader:

        inputs, targets = batch
        if use_gpu:
            inputs = inputs.cuda()
            targets = targets.cuda()

        inputs = Variable(inputs, volatile=True)
        targets = Variable(targets, volatile=True)
        output = model(inputs)
        output = criterion(output)

        predictions = output.max(dim=1)[1]

        for i in range(len(inputs)):
            score = output[i][targets[i]].data
            target = targets[i].data[0]
            pred = predictions[i].data[0]
            if target == pred:
                good.append((inputs[i].data.cpu().numpy(), score[0], target, pred))
            else:
                errors.append((inputs[i].data.cpu().numpy(), score[0], target, pred))

    return good, errors


def train(model, optimizer, dataset, n_epoch, batch_size, use_gpu=True, scheduler=None):
    history = History()

    criterion = nn.CrossEntropyLoss()

    dataset.transform = ToTensor()
    train_loader, val_loader = train_valid_loaders(dataset, batch_size=batch_size)

    for i in range(n_epoch):
        start = time.time()
        do_epoch(criterion, model, optimizer, scheduler, train_loader, use_gpu)
        end = time.time()

        train_acc, train_loss = validate(model, train_loader, use_gpu)
        val_acc, val_loss = validate(model, val_loader, use_gpu)
        history.save(train_acc, val_acc, train_loss, val_loss, optimizer.param_groups[0]['lr'])
        print('Epoch {} - Train acc: {:.2f} - Val acc: {:.2f} - Train loss: {:.4f} - Val loss: {:.4f} - Training time: {:.2f}s'.format(i,
                                                                                                              train_acc,
                                                                                                              val_acc,
                                                                                                              train_loss,
                                                                                                              val_loss, end - start))

    return history


def do_epoch(criterion, model, optimizer, scheduler, train_loader, use_gpu):
    model.train()
    if scheduler:
        scheduler.step()
    for batch in train_loader:

        inputs, targets = batch
        if use_gpu:
            inputs = inputs.cuda()
            targets = targets.cuda()

        inputs = Variable(inputs)
        targets = Variable(targets)
        optimizer.zero_grad()
        output = model(inputs)

        loss = criterion(output, targets)
        loss.backward()
        optimizer.step()


def test(model, test_dataset, batch_size, use_gpu=True):
    test_dataset.transform = ToTensor()
    sampler = SequentialSampler(test_dataset)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, sampler=sampler)

    score, loss = validate(model, test_loader, use_gpu=use_gpu)
    return score

if __name__ == '__main__':
    cifar_train, cifar_test = load_cifar10(path='./dataset/')
    model = CifarNet()
    model.cuda()

    batch_size = 32
    lr = 0.01
    n_epoch = 10

    model.load_state_dict(torch.load('./model/q1.pyt'))

    cifar_test.transform = ToTensor()
    loader, _ = train_valid_loaders(cifar_test, batch_size, train_split=1)
    good, bad = validate_ranking(model, loader, use_gpu=True)

