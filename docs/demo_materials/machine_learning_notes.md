# Machine Learning Demo Notes

## Backpropagation

Backpropagation is the training procedure used to compute how each model weight contributed to the prediction error. It applies the chain rule from the output layer back toward earlier layers. The key study idea is that gradients show the direction and size of the update needed to reduce loss.

Common mistakes:

- Forgetting that gradients are propagated backward through each layer.
- Mixing up the learning rate with the gradient itself.
- Updating weights before all required gradients are calculated.

Good revision practice:

- Draw a small network with one hidden layer.
- Compute one forward pass.
- Write the loss.
- Trace one gradient backward using the chain rule.
- Explain why the learning rate controls update size.

## Overfitting And Generalization

Overfitting happens when a model learns patterns that fit the training data too closely but do not generalize well to new data. A validation set helps detect overfitting because training accuracy may rise while validation performance gets worse.

Useful prevention methods include regularization, simpler models, more data, dropout, early stopping, and cross-validation.

