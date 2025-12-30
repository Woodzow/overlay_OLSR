# 根据具体的linktype和neighbortype生成一个字节长度的link_code

def create_link_code(link_type, neighbor_type):
    """
    生成 HELLO 消息所需的 Link Code 字节。
    
    根据 RFC 3626 Section 6.1.1:
    - Bit 0-1: Link Type
    - Bit 2-3: Neighbor Type
    - Bit 4-7: Reserved (必须为 0)
    
    :param link_type: 链路类型 (0-3)
    :param neighbor_type: 邻居类型 (0-3)
    :return: 组合后的 1 字节整数
    """
    # 简单的边界检查，确保输入值不超过 2 bit (0-3)
    if not (0 <= link_type <= 3):
        raise ValueError(f"Invalid Link Type: {link_type}. Must be 0-3.")
    if not (0 <= neighbor_type <= 3):
        raise ValueError(f"Invalid Neighbor Type: {neighbor_type}. Must be 0-3.")

    # 位操作逻辑：
    # 1. 取 neighbor_type，左移 2 位 (例如 1 -> 100)
    # 2. 与 link_type 进行按位或运算
    return (neighbor_type << 2) | link_type
