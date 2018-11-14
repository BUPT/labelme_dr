def simplify(points):
    if len(points) < 3:
        return None
    elif len(points) <= 5:
        return points
    flag = True
    while flag:
        flag = False
        for i in range(len(points) - 1):
            a = points[i]
            b = points[i + 1]
            dis = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
            if dis < 6:
                c = [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0]
                points.pop(i)
                points.pop(i)
                points.insert(i, c)
                if i < len(points) - 1:
                    flag = True
                break
        if len(points) <= 5:
            flag = False
    for i in range(len(points)):
        point = points[i]
        points[i] = [int(point[0]), int(point[1])]
    return points


points = [
        [
          1706,
          1122
        ],
        [
          1704,
          1124
        ],
        [
          1704,
          1125
        ],
        [
          1703,
          1126
        ],
        [
          1703,
          1131
        ],
        [
          1705,
          1133
        ],
        [
          1705,
          1134
        ],
        [
          1706,
          1135
        ],
        [
          1708,
          1135
        ],
        [
          1709,
          1136
        ],
        [
          1710,
          1136
        ],
        [
          1711,
          1135
        ],
        [
          1712,
          1135
        ],
        [
          1715,
          1132
        ],
        [
          1715,
          1131
        ],
        [
          1716,
          1130
        ],
        [
          1716,
          1129
        ],
        [
          1715,
          1128
        ],
        [
          1715,
          1126
        ],
        [
          1714,
          1126
        ],
        [
          1713,
          1125
        ],
        [
          1713,
          1124
        ],
        [
          1712,
          1123
        ],
        [
          1711,
          1123
        ],
        [
          1710,
          1122
        ]
      ]

new_points = simplify(points)
print(new_points)
