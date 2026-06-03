---
title: "RoCEv2 實戰：從參數設定到 rping 測試與封包分析"
date: 2026-06-03
description: "在 GB10 上用 ConnectX-7 實際操作 RoCEv2，介紹 GID 等關鍵參數、用 rping 驗證 RDMA 連線、ib_write_bw 跑 bandwidth test，並用 tcpdump capture RoCEv2 封包，比對 frame 結構與 RDMA CM 連線建立流程。"
tags:
  - rdma
  - rocev2
  - connectx-7
  - mellanox
  - nvidia-gb10
  - rping
  - tcpdump
  - packet-capture
  - high-performance-networking
  - infiniband-tools
  - ib-write-bw
keywords:
  - RoCEv2 parameters
  - RoCEv2 GID table
  - show_gids
  - ibdev2netdev
  - rping RDMA test
  - rdma link status
  - ConnectX-7 RoCE setup
  - RoCEv2 packet capture tcpdump
  - RDMA verification
  - ib_write_bw ib_send_bw
  - IB BTH Base Transport Header
  - RDMA Connection Manager
  - Queue Pair QP state machine
  - RDMA bandwidth benchmark
status: published
---

# RoCEv2 實戰：從參數設定到 rping 測試與封包分析

## 背景

上一篇介紹了 [RDMA 跟 GPUDirect 的底層原理](rdma-gpudirect-and-the-pcie-bar-rabbit-hole.md)，這篇接著講實際操作。目前市場主流是 RoCEv2，所以這邊用 RoCEv2 來示範。

環境是兩台 NVIDIA GB10，各有 4 個 PCIe 的 ConnectX-7 網卡，兩台之間用 RoCE port 直連。

## 環境確認

### 硬體

GB10 上看到的 4 張 ConnectX-7：

```console
sean@gb10-1:~$ lspci | grep Mellanox
0000:01:00.0 Ethernet controller: Mellanox Technologies MT2910 Family [ConnectX-7]
0000:01:00.1 Ethernet controller: Mellanox Technologies MT2910 Family [ConnectX-7]
0002:01:00.0 Ethernet controller: Mellanox Technologies MT2910 Family [ConnectX-7]
0002:01:00.1 Ethernet controller: Mellanox Technologies MT2910 Family [ConnectX-7]
```

### RDMA link 狀態

確認 RDMA link 是否正常：

```console
sean@gb10-1:~$ rdma link
link rocep1s0f0/1 state ACTIVE physical_state LINK_UP netdev enp1s0f0np0
link rocep1s0f1/1 state DOWN physical_state DISABLED netdev enp1s0f1np1
link roceP2p1s0f0/1 state ACTIVE physical_state LINK_UP netdev enP2p1s0f0np0
link roceP2p1s0f1/1 state DOWN physical_state DISABLED netdev enP2p1s0f1np1
```

2 個 port ACTIVE，2 個 DOWN（沒接線）。

### RDMA device 與 network interface 的 mapping

`ibdev2netdev` 可以看 RDMA device 跟 network interface 的對應關係：

```console
sean@gb10-1:~$ ibdev2netdev
rocep1s0f0 port 1 ==> enp1s0f0np0 (Up)
rocep1s0f1 port 1 ==> enp1s0f1np1 (Down)
roceP2p1s0f0 port 1 ==> enP2p1s0f0np0 (Up)
roceP2p1s0f1 port 1 ==> enP2p1s0f1np1 (Down)
```

## RoCEv2 關鍵參數

### GID (Global Identifier)

GID 是 RDMA 通訊中用來辨識 endpoint 的 identifier，類似 IP address 在 TCP/IP 中的角色。每個 RDMA port 會有一組 GID table，包含多個 entry。

用 `show_gids` 可以看完整的 GID table：

```console
sean@gb10-1:~$ show_gids
DEV     PORT    INDEX   GID                                     IPv4            VER     DEV
---     ----    -----   ---                                     ------------    ---     ---
rocep1s0f0      1       0       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v1      enp1s0f0np0
rocep1s0f0      1       1       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v2      enp1s0f0np0
rocep1s0f0      1       2       0000:0000:0000:0000:0000:ffff:c0a8:640a 192.168.100.10          v1      enp1s0f0np0
rocep1s0f0      1       3       0000:0000:0000:0000:0000:ffff:c0a8:640a 192.168.100.10          v2      enp1s0f0np0
rocep1s0f1      1       0       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v1      enp1s0f1np1
rocep1s0f1      1       1       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v2      enp1s0f1np1
roceP2p1s0f0    1       0       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v1      enP2p1s0f0np0
roceP2p1s0f0    1       1       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v2      enP2p1s0f0np0
roceP2p1s0f0    1       2       0000:0000:0000:0000:0000:ffff:c0a8:640e 192.168.100.14          v1      enP2p1s0f0np0
roceP2p1s0f0    1       3       0000:0000:0000:0000:0000:ffff:c0a8:640e 192.168.100.14          v2      enP2p1s0f0np0
roceP2p1s0f1    1       0       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v1      enP2p1s0f1np1
roceP2p1s0f1    1       1       fe80:0000:0000:0000:xxxx:xxxx:xxxx:xxxx                 v2      enP2p1s0f1np1
n_gids_found=12
```

幾個重點：

- **VER 欄位**：`v1` 是 RoCEv1（L2 only），`v2` 是 RoCEv2（L3 routable，走 UDP）。實際使用 RoCEv2 時，要選 `v2` 的 GID index。
- **IPv4 欄位**：有 IP 的 entry 是從對應 network interface 的 IP 衍生出來的，例如 `192.168.100.10` 對應 `enp1s0f0np0` 的 IP。
- **link-local（`fe80::` 開頭）**：自動生成的 link-local GID，由 NIC 的 MAC address 衍生而來，適用於同一 L2 segment 的通訊。
- **GID Index**：很多 RDMA 工具（例如 `ib_write_bw`、`ibv_rc_pingpong`）需要指定 GID index。RoCEv2 通常選有 IPv4 mapping 的 `v2` entry，以這台機器來說就是 index `3`。

## 用 rping 測試 RDMA 連線

確認參數之後，先用 `rping` 來驗證 RDMA connectivity。`rping` 是最簡單的工具，適合快速確認連線有沒有通。

### Server 端

先開 `tcpdump` capture RDMA traffic。如果 tcpdump 抓不到 RoCE packet，請參考 [在 NVIDIA GB10 上 compile 支援 RDMA sniffer 的 tcpdump](building-tcpdump-with-rdma-support-on-nvidia-gb10.md)。

```console
sean@gb10-1:~$ sudo tcpdump -i rocep1s0f0 -w dump.pcap
[sudo] password for sean:
tcpdump: listening on rocep1s0f0, link-type EN10MB (Ethernet), snapshot length 10000 bytes
205 packets captured
205 packets received by filter
0 packets dropped by kernel
```

開啟 rping server：

```console
sean@gb10-1:~$ rping -s -a 192.168.100.10
server DISCONNECT EVENT...
wait for RDMA_READ_ADV state 10
```

### Client 端

從另一台機器執行 rping，`-C 10` 表示 ping 10 次，`-v` 顯示詳細內容：

```console
sean@gb10-2:~$ rping -c -a 192.168.100.10 -C 10 -v
ping data: rdma-ping-0: ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqr
ping data: rdma-ping-1: BCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrs
ping data: rdma-ping-2: CDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrst
ping data: rdma-ping-3: DEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstu
ping data: rdma-ping-4: EFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuv
ping data: rdma-ping-5: FGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvw
ping data: rdma-ping-6: GHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwx
ping data: rdma-ping-7: HIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxy
ping data: rdma-ping-8: IJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz
ping data: rdma-ping-9: JKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyzA
client DISCONNECT EVENT...
```

10 次 RDMA ping 全部成功，每次 payload 都有 shifting pattern 的 ASCII 資料。`DISCONNECT EVENT` 代表 client 正常結束連線。

## 用 ib_write_bw 測試 RDMA Bandwidth

`rping` 只能驗證連線通不通，要看實際 throughput 就要用 `ib_write_bw`。

### Server 端

```console
sean@gb10-1:~$ ib_write_bw -d rocep1s0f0
```

### Client 端

`-D 10` 持續跑 10 秒，`--report_gbits` 以 Gbps 顯示，`--cpu_util` 同時顯示 CPU 使用率：

```console
sean@gb10-2:~$ ib_write_bw -d roceP2p1s0f0 -D 10 --cpu_util --report_gbits 192.168.100.10
---------------------------------------------------------------------------------------
                    RDMA_Write BW Test
 Dual-port       : OFF          Device         : roceP2p1s0f0
 Number of qps   : 1            Transport type : IB
 Connection type : RC           Using SRQ      : OFF
 PCIe relax order: ON
 ibv_wr* API     : ON
 TX depth        : 128
 CQ Moderation   : 1
 Mtu             : 1024[B]
 Link type       : Ethernet
 GID index       : 3
 Max inline data : 0[B]
 rdma_cm QPs     : OFF
 Data ex. method : Ethernet
---------------------------------------------------------------------------------------
 local address: LID 0000 QPN 0xxxxx PSN 0xxxxxx RKey 0xxxxxx VAddr 0xxxxxxxxxxx
 GID: 00:00:00:00:00:00:00:00:00:00:255:255:192:168:100:15
 remote address: LID 0000 QPN 0xxxxx PSN 0xxxxxx RKey 0xxxxxx VAddr 0xxxxxxxxxxx
 GID: 00:00:00:00:00:00:00:00:00:00:255:255:192:168:100:10
---------------------------------------------------------------------------------------
 #bytes     #iterations    BW peak[Gb/sec]    BW average[Gb/sec]   MsgRate[Mpps]    CPU_Util[%]
 65536      1059332          0.00               92.57              0.176557         5.07
---------------------------------------------------------------------------------------
```

幾個值得注意的點：

- **BW average 92.57 Gbps**：兩台 GB10 直連，ConnectX-7 跑出接近 100GbE line rate 的 throughput。
- **CPU_Util 5.07%**：RDMA 的 kernel bypass 效果很明顯，CPU 幾乎沒在做事，資料傳輸都由 RNIC 硬體處理。
- **GID index 3**：自動選了 `v2` 的 IPv4-mapped GID，跟前面 `show_gids` 看到的一致。
- **Connection type RC**：Reliable Connection，有 ACK 機制保證資料送達。
- **Mtu 1024**：這是 IB MTU，不是 Ethernet MTU。IB MTU 1024 bytes 是 RoCEv2 預設值。

## RoCEv2 封包分析

### Frame 結構比對

<figure markdown="span">
  ![RoCE & RoCEv2 Frame Structure](../assets/images/engineering/roce_02.png)
  <figcaption>RoCE & RoCEv2 Frame Structure</figcaption>
</figure>

用 Wireshark 打開 `dump.pcap`，可以看到實際 capture 到的 RoCEv2 frame：

<figure markdown="span">
  ![Wireshark 中的 RoCEv2 frame](../assets/images/engineering/rocev2_frame.png)
  <figcaption>Wireshark 中的 RoCEv2 frame</figcaption>
</figure>

比對這兩張圖可以確認：測試中傳輸的封包走的是 RoCEv2。最明顯的判斷依據是 **IP + UDP 的封裝結構** -- RoCEv1 直接跑在 Ethernet 上面，沒有 IP 跟 UDP layer；RoCEv2 則是封裝在 UDP (destination port 4791) 裡面，所以可以跨 L3 routing。

### IB BTH (Base Transport Header)

<figure markdown="span">
  ![IB BTH details](../assets/images/engineering/rocev2_frame_2.png)
  <figcaption>IB BTH (Base Transport Header)</figcaption>
</figure>

在 IP/UDP header 之後，就是 InfiniBand 的 BTH (Base Transport Header)。幾個重要欄位：

- **Opcode**：指定這個 packet 的 RDMA operation 類型，例如 RDMA_WRITE、RDMA_READ、SEND 等。
- **Destination QP**：目標端的 Queue Pair number，用來區分封包要送到哪一對 QP。
- **Acknowledge Request**：告訴接收端是否需要回傳 ACK。

### rping 在封包裡的實際 RDMA Operation

`rping` 的每一次 ping 會依序執行 3 種 RDMA operation：

1. **SEND**：client 先用 SEND 把 ping data 送到 server。SEND 是最基本的 RDMA operation，類似傳統 socket 的 send/recv，接收端需要預先 post 一個 Receive Work Request。
2. **RDMA_READ**：server 收到 SEND 後，用 RDMA_READ 直接從 client 的 memory 讀取資料。這個操作完全由 server 端的 RNIC 發起，client 的 CPU 不需要參與。
3. **RDMA_WRITE**：server 再用 RDMA_WRITE 把資料直接寫進 client 的 memory。跟 RDMA_READ 一樣，client 端的 CPU 完全不知道這件事發生了。

在 Wireshark 裡可以看到這些 operation 對應的 BTH Opcode，依序交替出現。這也是 `rping` 做為驗證工具的價值 -- 它不只測連線，還同時驗證了 SEND、RDMA_READ、RDMA_WRITE 三種核心 operation 都能正常運作。

### RoCEv2 Connection Manager 連線建立

<figure markdown="span">
  ![RoCEv2 Connection Manager flow](../assets/images/engineering/rocev2_protocol.png)
  <figcaption>RoCEv2 Connection Manager 握手流程</figcaption>
</figure>

圖中圈起來的部分是 RoCEv2 透過 RDMA Connection Manager (CM) 建立連線的流程。

跟 TCP/IP 比較的話，核心差異在於：**TCP 的連線建立是軟體跟 protocol stack 狀態的同步；RoCEv2 的連線建立是硬體 Queue Pair 資源的配置、狀態切換，以及 memory key 的交換。**

**TCP/IP：Three-way Handshake**

流程：`SYN → SYN-ACK → ACK`

- 同步雙方的 Initial Sequence Number (ISN)、確認 Window Size、協商 TCP option（MSS、SACK 等）。
- Kernel 在記憶體中配置 socket buffer。
- 連線的整個 lifecycle 都由 OS kernel 的 TCP/IP protocol stack 控制。

**RoCEv2：RDMA CM Handshake**

流程：`REQ → REP → RTU`

- **REQ (Connection Request)**：發起端帶上自己的 Queue Pair Number (QPN)、起始 Packet Sequence Number (PSN)、Private Data。
- **REP (Connection Reply)**：回應端收到後配置對應的硬體資源，回傳自己的 QPN 跟 PSN。
- **RTU (Ready to Use)**：發起端確認收到，通知雙方硬體已就緒，可以開始 RDMA 傳輸。

整個過程的核心是 **Queue Pair (QP)**，每個 QP 包含 Send Queue 跟 Receive Queue。連線建立之前，application 要先向 RNIC (RDMA NIC) 申請建立 QP，初始狀態是 RESET。

隨著 CM 流程推進，RNIC 上的硬體 state machine 會驅動 QP 進行狀態轉換：

```
RESET → INIT → RTR (Ready to Receive) → RTS (Ready to Send)
```

一旦進入 RTS 狀態，後續所有的資料傳輸完全由 RNIC 硬體處理，不再需要 OS kernel 跟 CPU 介入 -- 這就是 RDMA 的 zero-copy + kernel bypass。

## Key Takeaways

- **`rdma link` 跟 `ibdev2netdev`** 是確認 RDMA 環境最快的兩個 command。
- **GID table 是 RoCEv2 通訊的基礎**，用 `show_gids` 看。RoCEv2 要選 VER 為 `v2` 且有 IPv4 mapping 的 GID index。
- **`rping` 不只測連線** -- 它同時驗證 SEND、RDMA_READ、RDMA_WRITE 三種核心 operation。
- **`ib_write_bw` 跑出 92.57 Gbps，CPU 只用了 5%** -- RDMA 的 kernel bypass 讓 CPU 幾乎不需要參與資料傳輸。
- **tcpdump 可以 capture RoCE 封包**，但需要從 source compile 的版本。抓到的 `.pcap` 可以用 Wireshark 分析 RoCEv2 frame 結構。
- **RoCEv2 跟 RoCEv1 最明顯的差別是 IP + UDP 封裝**，讓 RDMA traffic 可以跨 L3 routing。
- **RoCEv2 的連線建立是硬體層級的資源配置**（QP allocation + state machine transition），跟 TCP 的軟體 protocol stack 同步完全不同。進入 RTS 後，資料傳輸完全由 RNIC 硬體接管。

## References

- [Mellanox OFED - show_gids documentation](https://docs.nvidia.com/networking/display/mlnxofedv24010331/show_gids)
- [rdma-core rping man page](https://man7.org/linux/man-pages/man1/rping.1.html)
- [Mellanox perftest (ib_write_bw)](https://github.com/linux-rdma/perftest)
- [RoCEv2 specification (IBTA)](https://www.roceinitiative.org/)
- [在 NVIDIA GB10 上 compile 支援 RDMA sniffer 的 tcpdump](building-tcpdump-with-rdma-support-on-nvidia-gb10.md)
- [RDMA、GPUDirect 與那個讓 GPU 變磚的 PCIe BAR 設定](rdma-gpudirect-and-the-pcie-bar-rabbit-hole.md)
