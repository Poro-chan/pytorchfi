#Train the model
import torch
import torch.nn as nn
import numpy as np
from core import FaultInjection

def train(model, device, train_loader, optimizer, epochs):
    loss_func = nn.CrossEntropyLoss()
    for epoch in range(epochs):
        print("\nEpoch: {}".format(epoch+1))
        model.train()
        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            outputs = model(data)
            if isinstance(outputs, tuple):
                output, aux_outputs = outputs
            else:
                output = outputs
            loss = loss_func(output, target)
            loss.backward()
            optimizer.step()
            if (batch_idx + 1) % 10 == 0:
                print(f'Epoch {epoch+1}, Batch {batch_idx+1}, Loss: {loss.item():.4f}')


# Evaluate the model
def evaluate(testloader, model, device):
  dataset_size = len(testloader.dataset)
  correct = 0
  model.eval()
  with torch.no_grad():
      for image, label in testloader:
          image, label = image.to(device), label.to(device)
          output = model(image)
          _, predicted = torch.max(output, 1)
          correct += torch.sum(predicted == label.data).item()

  print('Accuracy: {}/{} ({:.2f}%)\n'.format(
          correct, dataset_size, 100. * correct / dataset_size))

#custom function for bitflip and multiply values by 1+epsilon
class custom_func(FaultInjection):
    def __init__(self, model, batch_size, epsilon, index, **kwargs):
        super().__init__(model, batch_size, **kwargs)
        self.epsilon = epsilon
        self.index = index

    #single bitflip in 32-bit representation
    def single_bit_flip(self, module, input, output) :
        shape = output.shape
        output_cpu = output.detach().cpu()
        int32_output = output_cpu.numpy().view(np.int32)

        bit_mask = 1 << self.index
        int32_output = int32_output ^ bit_mask

        float_output = torch.from_numpy(int32_output.view(np.float32))
        try:
            # Reshape back to the original shape
            float_output = float_output.reshape(shape)
        except RuntimeError as e:
            print(f"Error during reshape: {e}")
            print(f"Expected shape: {shape}, Actual size: {float_output.numel()}")
            print(f"Original output size: {output.numel()}, int32_output size: {int32_output.size}")
            return

        if output.is_cuda :
            output.data.copy_(float_output.to(output.device))
        else:
            output.data.copy_(float_output)

        self.update_layer()
        if self.current_layer >= self.get_total_layers():
            self.reset_current_layer()
    
    #mutiply all output by a factor
    def multiply_output(self, module, input, output) :
        output[:] = output * (1+self.epsilon)

        self.update_layer()
        if self.current_layer >= self.get_total_layers():
            self.reset_current_layer()

    #multiply only one value by a factor
    #see whats more vulnerable test multiple things: eg 1 value per layer fixed/random or all values for one layer 
    def multiply_value(self, module, input, output) :
        output[self.index] = output * (1+self.epsilon)

        self.update_layer()
        if self.current_layer >= self.get_total_layers():
            self.reset_current_layer()

    def multiply_value_layer(self, module, input, output) :
        if(self.index == self.current_layer) :
            output[:] = output * (1+self.epsilon)

        self.update_layer()
        if self.current_layer >= self.get_total_layers():
            self.reset_current_layer()

    def multiply_one_value_layer(self, module, input, output) :
        output[self.index] = output[self.index] * (1+self.epsilon)

        self.update_layer()
        if self.current_layer >= self.get_total_layers():
            self.reset_current_layer()