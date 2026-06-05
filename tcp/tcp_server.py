import socket, struct, hashlib, os, time, json, zlib, argparse
MATRICULA="20249016095"; NOME="Lucas Araújo Moura"
AUTH_HASH=hashlib.sha256((MATRICULA+NOME).encode()).hexdigest()
HOST="0.0.0.0"; PORT=9001; BUFFER_SIZE=4096; OUTPUT_DIR="received"
HEADER_FORMAT="!HBBIII64sI"; HEADER_SIZE=struct.calcsize(HEADER_FORMAT)
MAGIC=0xA7B3; VERSION=0x01; MSG_DATA=0x01; MSG_FIN=0x02

def parse_header(raw):
    magic,version,msg_type,seq_num,total_size,chunk_size,auth_bytes,checksum=struct.unpack(HEADER_FORMAT,raw[:HEADER_SIZE])
    return {"magic":magic,"version":version,"msg_type":msg_type,"seq_num":seq_num,"total_size":total_size,"chunk_size":chunk_size,"auth":auth_bytes.decode("ascii").rstrip("\x00"),"checksum":checksum}

def recv_exact(conn,n):
    data=b""
    while len(data)<n:
        chunk=conn.recv(n-len(data))
        if not chunk: raise ConnectionError("Conexão encerrada")
        data+=chunk
    return data

def handle_client(conn,addr,log_path):
    print(f"\n[TCP-SERVER] Conexão de {addr}")
    os.makedirs(OUTPUT_DIR,exist_ok=True)
    try:
        raw_header=recv_exact(conn,HEADER_SIZE)
        hdr=parse_header(raw_header)
        if hdr["magic"]!=MAGIC: return
        if hdr["auth"]!=AUTH_HASH: print("[TCP-SERVER] Auth inválido!"); return
        total_size=hdr["total_size"]
        filename_raw=recv_exact(conn,256)
        filename=filename_raw.decode("utf-8").rstrip("\x00")
        output_path=os.path.join(OUTPUT_DIR,os.path.basename(filename))
        received=0; start_time=time.perf_counter()
        with open(output_path,"wb") as f:
            while received<total_size:
                raw_hdr=recv_exact(conn,HEADER_SIZE)
                hdr=parse_header(raw_hdr)
                if hdr["msg_type"]==MSG_FIN: break
                csize=hdr["chunk_size"]
                payload=recv_exact(conn,csize)
                calc_crc=zlib.crc32(payload)&0xFFFFFFFF
                if calc_crc!=hdr["checksum"]: print(f"[TCP-SERVER] WARN checksum chunk {hdr['seq_num']}")
                f.write(payload); received+=csize
        elapsed=time.perf_counter()-start_time
        throughput=(received*8)/elapsed/1_000_000
        print(f"[TCP-SERVER] OK | {received}b | {elapsed:.4f}s | {throughput:.4f} Mbps")
        os.makedirs(os.path.dirname(log_path) or ".",exist_ok=True)
        with open(log_path,"a") as lf:
            lf.write(json.dumps({"protocol":"TCP","bytes":received,"time_s":elapsed,"throughput_mbps":throughput,"timestamp":time.time()})+"\n")
    except Exception as e: print(f"[TCP-SERVER] Erro: {e}")
    finally: conn.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=PORT)
    parser.add_argument("--log",type=str,default="/app/logs/tcp_server.log")
    args=parser.parse_args()
    print(f"TCP SERVER | {NOME} | Auth: {AUTH_HASH[:16]}... | Porta: {args.port}")
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        srv.bind((HOST,args.port)); srv.listen(5)
        print(f"[TCP-SERVER] Aguardando em {HOST}:{args.port}...")
        while True:
            conn,addr=srv.accept()
            handle_client(conn,addr,args.log)

if __name__=="__main__": main()
