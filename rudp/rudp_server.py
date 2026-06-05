import socket, struct, hashlib, os, time, json, zlib, argparse
MATRICULA="20249016095"; NOME="Lucas Araújo Moura"
AUTH_HASH=hashlib.sha256((MATRICULA+NOME).encode()).hexdigest()
HOST="0.0.0.0"; PORT=9002; OUTPUT_DIR="/app/received"
HEADER_FORMAT="!HBBIII64sI"; HEADER_SIZE=struct.calcsize(HEADER_FORMAT)
MAGIC=0xA7B3; MSG_DATA=0x01; MSG_FIN=0x02; MSG_ACK=0x03; MSG_NACK=0x04; MSG_HELLO=0x05; MSG_HELLO_ACK=0x06

def bh(mt,sq,ts,cs,ck):
    ab=AUTH_HASH.encode("ascii")[:64].ljust(64,b"\x00")
    return struct.pack(HEADER_FORMAT,MAGIC,0x01,mt,sq,ts,cs,ab,ck)

def ph(raw):
    mg,vr,mt,sq,ts,cs,ab,ck=struct.unpack(HEADER_FORMAT,raw[:HEADER_SIZE])
    return {"magic":mg,"msg_type":mt,"seq_num":sq,"total_size":ts,"chunk_size":cs,"auth":ab.decode("ascii").rstrip("\x00"),"checksum":ck}

def run_server(port,log_path):
    os.makedirs(OUTPUT_DIR,exist_ok=True)
    os.makedirs(os.path.dirname(log_path),exist_ok=True)
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind((HOST,port))
    print(f"R-UDP SERVER | {NOME} | Auth: {AUTH_HASH[:16]}... | Porta: {port}")
    print(f"[RUDP-SERVER] Aguardando em {HOST}:{port}...")
    while True:
        sock.settimeout(None)
        try:
            raw,addr=sock.recvfrom(HEADER_SIZE+256)
            if len(raw)<HEADER_SIZE: continue
            hdr=ph(raw[:HEADER_SIZE])
            if hdr["magic"]!=MAGIC or hdr["msg_type"]!=MSG_HELLO or hdr["auth"]!=AUTH_HASH: continue
            ts=hdr["total_size"]
            fn=raw[HEADER_SIZE:HEADER_SIZE+256].decode("utf-8").rstrip("\x00")
            op=os.path.join(OUTPUT_DIR,os.path.basename(fn))
            sock.sendto(bh(MSG_HELLO_ACK,0,ts,0,0),addr)
            print(f"[RUDP-SERVER] HELLO de {addr} | {fn} ({ts}b)")
            sock.settimeout(10.0)
            eq=1; rv=0; rt=0; st=time.perf_counter()
            with open(op,"wb") as f:
                while rv<ts:
                    try: rp,pa=sock.recvfrom(HEADER_SIZE+8192)
                    except socket.timeout: break
                    if pa!=addr or len(rp)<HEADER_SIZE: continue
                    hdr=ph(rp[:HEADER_SIZE]); pl=rp[HEADER_SIZE:]
                    if hdr["msg_type"]==MSG_FIN:
                        sock.sendto(bh(MSG_ACK,hdr["seq_num"],ts,0,0),addr); break
                    if hdr["msg_type"]!=MSG_DATA: continue
                    cs=hdr["chunk_size"]; pl=pl[:cs]
                    crc=zlib.crc32(pl)&0xFFFFFFFF
                    if crc!=hdr["checksum"]:
                        sock.sendto(bh(MSG_NACK,hdr["seq_num"],ts,0,0),addr); rt+=1; continue
                    if hdr["seq_num"]<eq:
                        sock.sendto(bh(MSG_ACK,hdr["seq_num"],ts,0,0),addr); continue
                    f.write(pl); rv+=cs; eq+=1
                    sock.sendto(bh(MSG_ACK,hdr["seq_num"],ts,0,0),addr)
            el=time.perf_counter()-st
            tp=(rv*8)/el/1e6 if el>0 else 0
            print(f"[RUDP-SERVER] OK: {rv}b | {tp:.4f} Mbps | retrans={rt}")
            with open(log_path,"a") as lf:
                lf.write(json.dumps({"protocol":"RUDP","bytes":rv,"retransmissions":rt,"time_s":el,"throughput_mbps":tp,"timestamp":time.time()})+"\n")
        except Exception as e: print(f"[RUDP-SERVER] Erro: {e}"); continue

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=PORT)
    parser.add_argument("--log",type=str,default="/app/logs/rudp_server.log")
    args=parser.parse_args()
    run_server(args.port,args.log)

if __name__=="__main__": main()
