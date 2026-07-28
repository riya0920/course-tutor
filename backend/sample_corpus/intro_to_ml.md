# Introduction to Machine Learning (Sample Course)

## Supervised Learning
Supervised Learning is a paradigm where a model learns a mapping from inputs to
outputs using labeled examples. Each training example is a pair of an input
feature vector and a target label. Common tasks are classification (predicting a
discrete label) and regression (predicting a continuous value). The model is
trained by minimizing a loss function that measures the gap between predictions
and true labels.

## Unsupervised Learning
Unsupervised Learning finds structure in data that has no labels. Instead of
predicting a target, the model groups or compresses the data. Clustering and
dimensionality reduction are the two most common unsupervised tasks.

## Classification and Regression
Classification predicts a discrete category, such as spam or not spam.
Regression predicts a continuous number, such as the price of a house. A
classification model often outputs a probability for each class, while a
regression model outputs a real-valued estimate.

## Train, Validation, and Test Sets
Data is split into three parts. The training set fits the model, the validation
set tunes hyperparameters and detects overfitting, and the test set gives a
final unbiased estimate of performance. The test set must never be used during
training or tuning.

## Overfitting and Underfitting
Overfitting occurs when a model captures noise in the training data rather than
the underlying pattern, so it performs well on training data but poorly on
unseen data. Underfitting is the opposite: the model is too simple to capture
the pattern and performs poorly even on the training data.

## Regularization
Regularization combats overfitting by penalizing model complexity. L2
Regularization adds the squared magnitude of the weights to the loss and shrinks
weights smoothly toward zero. L1 Regularization adds the absolute magnitude of
the weights and tends to produce sparse weights, driving some exactly to zero.
The regularization strength is controlled by a coefficient often called lambda.

## Gradient Descent
Gradient Descent is an optimization algorithm that iteratively adjusts model
parameters in the direction that reduces the loss. The Learning Rate controls
the size of each step. If the learning rate is too large, training can diverge;
if it is too small, training is slow. The gradient points in the direction of
steepest increase, so the update moves in the opposite direction.

## Stochastic Gradient Descent
Stochastic Gradient Descent estimates the gradient from a small batch of
examples rather than the full dataset, which speeds up training on large
datasets. The batch size is the number of examples used to compute each update.
Smaller batches give noisier but faster updates.

## Neural Networks
A Neural Network is composed of layers of interconnected units called neurons.
Each neuron computes a weighted sum of its inputs followed by a nonlinear
Activation Function. An input layer receives the features, one or more hidden
layers transform them, and an output layer produces the prediction.

## Activation Functions
An Activation Function introduces nonlinearity so a network can model complex
relationships. ReLU outputs the input if it is positive and zero otherwise. The
sigmoid squashes values into the range zero to one. Without a nonlinear
activation, stacking layers would collapse into a single linear function.

## Backpropagation
Backpropagation is the algorithm that computes gradients of the loss with
respect to every weight by applying the chain rule backward through the network.
These gradients are then used by gradient descent to update the weights.

## Bias and Variance
The Bias Variance Tradeoff describes the tension between two sources of error.
High Bias means the model is too simple and underfits. High Variance means the
model is too sensitive to the training data and overfits. Good generalization
requires balancing bias and variance.

## Decision Trees
A Decision Tree splits the data by asking a sequence of questions about the
features, forming a tree of decisions that ends in a prediction at each leaf.
Trees are easy to interpret but can overfit if grown too deep. The depth of the
tree is a key hyperparameter.

## Random Forests
A Random Forest is an ensemble of many decision trees trained on random subsets
of the data and features. Averaging their predictions reduces variance and
usually improves accuracy over a single tree.

## k-Nearest Neighbors
k-Nearest Neighbors classifies a new point by looking at the k closest training
points and taking a majority vote of their labels. It does no explicit training
step; all computation happens at prediction time. The choice of k trades off
noise sensitivity against smoothness.

## Support Vector Machines
A Support Vector Machine finds the hyperplane that separates classes with the
largest possible margin. The points closest to the boundary are called support
vectors. A kernel function lets the model separate classes that are not linearly
separable.

## k-Means Clustering
k-Means Clustering partitions data into k groups by iteratively assigning each
point to the nearest cluster center and then moving each center to the mean of
its assigned points. It is an unsupervised algorithm and requires choosing k in
advance.

## Principal Component Analysis
Principal Component Analysis is a dimensionality reduction technique that
projects data onto the directions of greatest variance, called principal
components. It is used to compress features while keeping as much information as
possible.

## Cross-Validation
Cross-Validation estimates model performance by splitting the data into k folds,
training on k minus one folds and validating on the remaining fold, then
rotating. Averaging the scores gives a more reliable estimate than a single
split.

## Precision, Recall, and F1
Precision is the fraction of predicted positives that are actually positive.
Recall is the fraction of actual positives that were correctly predicted. The F1
score is the harmonic mean of precision and recall, balancing the two.

## Confusion Matrix
A Confusion Matrix is a table that counts true positives, false positives, true
negatives, and false negatives. It is the basis for computing precision, recall,
and accuracy.

## Feature Scaling
Feature Scaling puts features on a comparable range so that no single feature
dominates because of its units. Standardization rescales a feature to zero mean
and unit variance, while normalization rescales values into a fixed range such
as zero to one. Distance-based methods like k-Nearest Neighbors are sensitive to
scaling.

## Loss Functions
A Loss Function measures how wrong a prediction is. Mean Squared Error is common
for regression and averages the squared differences between predictions and
targets. Cross-Entropy Loss is common for classification and penalizes confident
wrong predictions heavily.

## Softmax
The Softmax function converts a vector of scores into a probability distribution
over classes, where the probabilities are positive and sum to one. It is
typically used in the output layer of a classifier.

## Dropout
Dropout is a regularization technique for neural networks that randomly disables
a fraction of neurons during each training step. This prevents the network from
relying too heavily on any single neuron and reduces overfitting.

## Overfitting Detection
Overfitting is detected when training accuracy keeps improving while validation
accuracy stops improving or gets worse. The gap between training and validation
performance is a signal of overfitting.
