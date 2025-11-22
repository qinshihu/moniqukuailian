import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request

# ====================== 1. 区块链核心类 ======================
class Blockchain:
    def __init__(self):
        self.chain = []  # 存储区块链
        self.current_transactions = []  # 待打包的交易
        self.nodes = set()  # 存储网络中的节点（去中心化特性）

        # 创建创世区块（第一个区块，无前置区块）
        self.new_block(previous_hash='1', proof=100)

    # 注册节点（模拟去中心化网络）
    def register_node(self, address):
        self.nodes.add(address)

    # 验证区块链有效性（哈希值+工作量证明是否合法）
    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            # 1. 验证当前区块的前哈希是否等于前区块的哈希
            if block['previous_hash'] != self.hash(last_block):
                return False

            # 2. 验证工作量证明是否合法
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    # 共识算法：解决节点间区块链不一致问题（取最长有效链）
    def resolve_conflicts(self):
        neighbors = self.nodes
        new_chain = None

        # 只关注比当前长的链
        max_length = len(self.chain)

        # 遍历所有邻居节点，获取其区块链并验证
        for node in neighbors:
            response = request.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json['length']
                chain = response.json['chain']

                # 如果对方链更长且有效，则更新本地链
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # 如果找到更长的有效链，则替换本地链
        if new_chain:
            self.chain = new_chain
            return True
        return False

    # 创建新区块并添加到链
    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,  # 区块索引
            'timestamp': time(),  # 时间戳（Unix时间）
            'transactions': self.current_transactions,  # 交易记录
            'proof': proof,  # 工作量证明结果
            'previous_hash': previous_hash or self.hash(self.chain[-1]),  # 前区块哈希
        }

        # 清空待打包交易
        self.current_transactions = []
        self.chain.append(block)
        return block

    # 添加新交易（转账记录）
    def new_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,  # 发送者地址（UUID）
            'recipient': recipient,  # 接收者地址（UUID）
            'amount': amount,  # 转账金额
        })
        # 返回当前交易所在的区块索引（下一个要打包的区块）
        return self.last_block['index'] + 1

    # 计算区块的SHA-256哈希值（核心加密步骤）
    @staticmethod
    def hash(block):
        # 将区块字典转换为有序JSON字符串（避免哈希不一致）
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    # 获取最后一个区块
    @property
    def last_block(self):
        return self.chain[-1]

    # 工作量证明（PoW）：找到一个数字p'，使得hash(pp')前n位为0
    def proof_of_work(self, last_proof):
        proof = 0
        # 循环计算，直到找到满足条件的proof
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    # 验证工作量证明：hash(last_proof, proof)前4位是否为0
    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"  # 难度：前4位为0（可调整位数提高难度）

# ====================== 2.  Flask接口（模拟节点API） ======================
app = Flask(__name__)

# 生成节点唯一标识（模拟钱包地址）
node_identifier = str(uuid4()).replace('-', '')

# 初始化区块链
blockchain = Blockchain()

# 接口1：挖矿（获取奖励）
@app.route('/mine', methods=['GET'])
def mine():
    # 1. 执行工作量证明，获取新的proof
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # 2. 挖矿奖励：发送者为"0"表示系统奖励
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,  # 奖励1个代币
    )

    # 3. 创建新区块并添加到链
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    # 4. 返回结果
    response = {
        'message': "新区块已挖出",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

# 接口2：创建交易（转账）
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # 验证请求参数是否完整
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return '参数缺失', 400

    # 添加交易到待打包列表
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'交易将被打包到区块 #{index}'}
    return jsonify(response), 201

# 接口3：查看完整区块链
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

# 接口4：注册节点（模拟去中心化网络）
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')

    if nodes is None:
        return "错误：请提供有效的节点列表", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': '新节点已注册',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

# 接口5：共识机制（解决节点冲突）
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': '区块链已更新为最长有效链',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': '当前区块链已是最长有效链',
            'chain': blockchain.chain
        }
    return jsonify(response), 200

# 启动服务
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)