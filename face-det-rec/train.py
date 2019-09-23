"""
Train SVM- and XGBoost-based face classifiers from 128-d face encodings.

Part of the smart-zoneminder project:
See https://github.com/goruck/smart-zoneminder.

Copyright (c) 2019 Lindo St. Angel
"""

import pickle
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix
from xgboost import XGBClassifier as xgb

# Path to known face encodings.
# The pickle file needs to be generated by the 'encode_faces.py' program first.
KNOWN_FACE_ENCODINGS_PATH = '/home/lindo/develop/smart-zoneminder/face-det-rec/encodings.pickle'
# Where to save SVM model.
SVM_MODEL_PATH = '/home/lindo/develop/smart-zoneminder/face-det-rec/svm_face_recognizer.pickle'
# Where to save XGBoost model.
XGB_MODEL_PATH = '/home/lindo/develop/smart-zoneminder/face-det-rec/xgb_face_recognizer.pickle'
# Where to save label encoder.
LABEL_PATH = '/home/lindo/develop/smart-zoneminder/face-det-rec/face_labels.pickle'

# Define a seed so random operations are the same from run to run.
RANDOM_SEED = 1234

# Define number of folds for the Stratified K-Folds cross-validator.
FOLDS = 5

# Number of parameters to combine for xgb random search. 
PARA_COMB = 20

# Load the known faces and embeddings.
with open(KNOWN_FACE_ENCODINGS_PATH, 'rb') as fp:
    data_pickle = pickle.load(fp)

# Encodings are stored as a list of 128-d numpy arrays, convert to 2D array.
data = np.array(data_pickle['encodings'])
#print('data {}'.format(data))

# Encode the labels.
print('Encoding labels...')
le = LabelEncoder()
labels = le.fit_transform(data_pickle['names'])
#print('labels {}'.format(labels))

def find_best_svm_estimator(X, y, cv, random_seed):
    # Exhaustive search over specified parameter values for svm.
    # Returns optimized svm estimator.
    print('\n Finding best svm estimator...')
    Cs = [0.001, 0.01, 0.1, 1, 10, 100]
    gammas = [0.001, 0.01, 0.1, 1, 10, 100]
    param_grid = [
        {'C': Cs, 'kernel': ['linear']},
        {'C': Cs, 'gamma': gammas, 'kernel': ['rbf']}]
    init_est = SVC(probability=True, class_weight='balanced',
        random_state=random_seed, verbose=False)
    grid_search = GridSearchCV(estimator=init_est, param_grid=param_grid,
        verbose=1, n_jobs=4, iid=False, cv=cv)
    grid_search.fit(X, y)
    #print('\n All results:')
    #print(grid_search.cv_results_)
    print('\n Best estimator:')
    print(grid_search.best_estimator_)
    print('\n Best score for {}-fold search:'.format(FOLDS))
    print(grid_search.best_score_)
    print('\n Best hyperparameters:')
    print(grid_search.best_params_)
    return grid_search.best_estimator_

def find_best_xgb_estimator(X, y, cv, param_comb, random_seed):
    # Random search over specified parameter values for XGBoost.
    # Exhaustive search takes many more cycles w/o much benefit.
    # Returns optimized XGBoost estimator.
    # Ref: https://www.kaggle.com/tilii7/hyperparameter-grid-search-with-xgboost
    print('\n Finding best XGBoost estimator...')
    param_grid = {
        'min_child_weight': [1, 5, 10],
        'gamma': [0.5, 1, 1.5, 2, 5],
        'subsample': [0.6, 0.8, 1.0],
        'colsample_bytree': [0.6, 0.8, 1.0],
        'max_depth': [3, 4, 5]
        }
    init_est = xgb(learning_rate=0.02, n_estimators=600, objective='multi:softprob',
        verbose=1, n_jobs=1, random_state=random_seed)
    random_search = RandomizedSearchCV(estimator=init_est, param_distributions=param_grid,
        n_iter=param_comb, n_jobs=4, iid=False, cv=cv,
        verbose=1, random_state=random_seed)
    random_search.fit(X, y)
    #print('\n All results:')
    #print(random_search.cv_results_)
    print('\n Best estimator:')
    print(random_search.best_estimator_)
    print('\n Best score for {}-fold search with {} parameter combinations:'
        .format(FOLDS, PARA_COMB))
    print(random_search.best_score_)
    print('\n Best hyperparameters:')
    print(random_search.best_params_)
    return random_search.best_estimator_

# Split data up into train and test sets.
(X_train, X_test, y_train, y_test) = train_test_split(
    data, labels, test_size=0.20, random_state=RANDOM_SEED, shuffle=True)
#print('X_train: {} X_test: {} y_train: {} y_test: {}'.format(X_train, X_test, y_train, y_test))

skf = StratifiedKFold(n_splits=FOLDS)

target_names = list(le.classes_)

# Find best svm classifier, evaluate and then save it.
best_svm = find_best_svm_estimator(X_train, y_train, skf.split(X_train, y_train), RANDOM_SEED)
print('\n Evaluating svm model...')
y_pred = best_svm.predict(X_test)
print('\n Confusion matrix:')
print(confusion_matrix(y_test, y_pred))
print('\n Classification matrix:')
print(classification_report(y_test, y_pred, target_names=target_names))
print('\n Saving svm model...')
with open(SVM_MODEL_PATH, 'wb') as outfile:
    outfile.write(pickle.dumps(best_svm))

# Find best XGBoost classifier, evaluate and save it. 
best_xgb = find_best_xgb_estimator(X_train, y_train, skf.split(X_train, y_train),
    PARA_COMB, RANDOM_SEED)
print('\n Evaluating xgb model...')
y_pred = best_xgb.predict(X_test)
print('\n Confusion matrix:')
print(confusion_matrix(y_test, y_pred))
print('\n Classification matrix:')
print(classification_report(y_test, y_pred, target_names=target_names))
print('\n Saving xgb model...')
with open(XGB_MODEL_PATH, 'wb') as outfile:
    outfile.write(pickle.dumps(best_xgb))

# Write the label encoder to disk.
print('\n Saving label encoder...')
with open(LABEL_PATH, 'wb') as outfile:
    outfile.write(pickle.dumps(le))