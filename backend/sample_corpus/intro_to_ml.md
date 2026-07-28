# Introduction to Machine Learning (Sample Course)

## Supervised Learning
Supervised Learning is a paradigm where a model learns a mapping from inputs to
outputs using labeled examples. Each training example is a pair of an input
feature vector and a target label. Common tasks are classification (predicting a
discrete label) and regression (predicting a continuous value). The model is
trained by minimizing a loss function that measures the gap between predictions
and true labels.

## Overfitting and Regularization
Overfitting occurs when a model captures noise in the training data rather than
the underlying pattern, so it performs well on training data but poorly on
unseen data. Regularization combats overfitting by penalizing model complexity.
L2 Regularization adds the squared magnitude of the weights to the loss, while
L1 Regularization adds the absolute magnitude and tends to produce sparse
weights. A validation set held out from training is used to detect overfitting.

## Gradient Descent
Gradient Descent is an optimization algorithm that iteratively adjusts model
parameters in the direction that reduces the loss. The Learning Rate controls
the size of each step. If the learning rate is too large, training can diverge;
if it is too small, training is slow. Stochastic Gradient Descent estimates the
gradient from a small batch of examples rather than the full dataset, which
speeds up training on large datasets.

## Neural Networks
A Neural Network is composed of layers of interconnected units called neurons.
Each neuron computes a weighted sum of its inputs followed by a nonlinear
Activation Function such as ReLU or the sigmoid. Backpropagation is the
algorithm that computes gradients of the loss with respect to every weight by
applying the chain rule backward through the network.

## Bias and Variance
The Bias Variance Tradeoff describes the tension between two sources of error.
High Bias means the model is too simple and underfits. High Variance means the
model is too sensitive to the training data and overfits. Good generalization
requires balancing bias and variance.
