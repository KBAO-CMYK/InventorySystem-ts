import pandas as pd

inp = "/Users/sh23/Desktop/dev/12.4/operation_record.csv"

df = pd.read_csv(inp)

# 替换操作时间列中的/为-
df['操作时间'] = df['操作时间'].str.replace('/', '-')
print("\n替换指定列（操作时间）后的DataFrame：")
print(df['操作时间'])

# 新增：保存修改后的文件（默认覆盖原文件，index=False不保存多余的索引列）
df.to_csv(inp, index=False, encoding='utf-8')
print(f"\n修改后的文件已保存至：{inp}")

