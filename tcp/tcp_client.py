import socket, struct, hashlib, os, time, json, zlib, argparse
MATRICULA="20249016095"; NOME="Lucas Araújo Moura"
AUTH_HASH=hashlib.sha256((MATRICULA+NOME).encode()).hexdigest()
SERVER_HOST="127.0.0.1"; SERVER_PORT=9001; CHUNK_SIZE=4096
HEADER_FORMAT="!HBBIII64sI"; HEADER_SIZE=struct.calcsize(HEADER_FORMAT)
MAGIC=0xA7B3; MSG_DATA=0x01; MSG_FIN=0x02

def build_header(msg_type,seq_num,total_size,chunk_size,checksum):
    auth_bytes=AUTH_HASH.encode("ascii")[:64].ljust(64,b"\x00")
    return struct.pack(HEADER_FORMAT,MAGIC,0x01,msg_type,seq_num,total_size,chunk_size,auth_bytes,checksum)

def send_file(host,port,filepath,log_path,run_id=0):
    if not os.path.isfile(filepath): print(f"Arquivo não encontrado: {filepath}"); return
    total_size=os.path.getsize(filepath)
    filename=os.path.basename(filepath)
    print(f"\n[TCP-CLIENT] Enviando '{filename}' ({total_size}b) → {host}:{port}")
    print(f"[TCP-CLIENT] X-Custom-Auth: {AUTH_HASH[:16]}...")
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.connect((host,port))
        sock.sendall(build_header(MSG_DATA,0,total_size,0,0))
        sock.sendall(filename.encode("utf-8")[:256].ljust(256,b"\x00"))
        seq=1; sent=0; start_time=time.perf_counter()
        with open(filepath,"rb") as f:
            while True:
                payload=f.read(CHUNK_SIZE)
                if not payload: break
                checksum=zlib.crc32(payload)&0xFFFFFFFF
                sock.sendall(build_header(MSG_DATA,seq,total_size,len(payload),checksum)+payload)
                sent+=len(payload); seq+=1
                if seq%100==0: print(f"[TCP-CLIENT] Chunk {seq} | {sent}/{total_size}")
        sock.sendall(build_header(MSG_FIN,seq,total_size,0,0))
        elapsed=time.perf_counter()-start_time
        throughput=(sent*8)/elapsed/1_000_000
        print(f"[TCP-CLIENT] Completo! | {sent}b | {elapsed:.4f}s | {throughput:.4f} Mbps")
        os.makedirs(os.path.dirname(log_path),exist_ok=True)
        with open(log_path,"a") as lf:
            lf.write(json.dumps({"run_id":run_id,"protocol":"TCP","file":filename,"bytes":sent,"time_s":elapsed,"throughput_mbps":throughput,"timestamp":time.time()})+"\n")
        return throughput

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--host",default=SERVER_HOST)
    parser.add_argument("--port",type=int,default=SERVER_PORT)
    parser.add_argument("--log",default="/app/logs/tcp_client.log")
    parser.add_argument("--run",type=int,default=0)
    args=parser.parse_args()
    print(f"TCP CLIENT | {NOME} | Chunk: {CHUNK_SIZE}b | Header: {HEADER_SIZE}b")
    send_file(args.host,args.port,args.file,args.log,args.run)

if __name__=="__main__": main()
