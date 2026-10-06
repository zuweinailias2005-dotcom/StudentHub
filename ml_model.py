from sklearn.tree import DecisionTreeClassifier


# Training data
# [attendance, average_marks, assignment_completion]

X = [
    [90, 85, 95],
    [85, 80, 90],
    [95, 92, 98],
    [80, 75, 85],

    [70, 65, 70],
    [65, 60, 65],
    [75, 68, 72],
    [60, 62, 70],

    [50, 45, 40],
    [55, 50, 45],
    [45, 40, 35],
    [40, 35, 30]
]


# 0 = High Risk
# 1 = Medium Risk
# 2 = Low Risk

y = [
    2, 2, 2, 2,
    1, 1, 1, 1,
    0, 0, 0, 0
]


model = DecisionTreeClassifier(random_state=42)

model.fit(X, y)


def predict_risk(attendance, marks, assignments):

    prediction = model.predict([
        [attendance, marks, assignments]
    ])

    if prediction[0] == 0:
        return "High Risk"

    elif prediction[0] == 1:
        return "Medium Risk"

    else:
        return "Low Risk"