import socket, struct, hashlib, os, time, json, zlib, argparse
MATRICULA="20249016095"; NOME="Lucas Araújo Moura"
AUTH_HASH=hashlib.sha256((MATRICULA+NOME).encode()).hexdigest()
SERVER_HOST="127.0.0.1"; SERVER_PORT=9002; CHUNK_SIZE=4096; TIMEOUT=1.0; MAX_RETRIES=10
HEADER_FORMAT="!HBBIII64sI"; HEADER_SIZE=struct.calcsize(HEADER_FORMAT)
MAGIC=0xA7B3; MSG_DATA=0x01; MSG_FIN=0x02; MSG_ACK=0x03; MSG_NACK=0x04; MSG_HELLO=0x05; MSG_HELLO_ACK=0x06

def bh(mt,sq,ts,cs,ck):
    ab=AUTH_HASH.encode("ascii")[:64].ljust(64,b"\x00")
    return struct.pack(HEADER_FORMAT,MAGIC,0x01,mt,sq,ts,cs,ab,ck)

def ph(raw):
    mg,vr,mt,sq,ts,cs,ab,ck=struct.unpack(HEADER_FORMAT,raw[:HEADER_SIZE])
    return {"magic":mg,"msg_type":mt,"seq_num":sq,"total_size":ts,"chunk_size":cs,"auth":ab.decode("ascii").rstrip("\x00"),"checksum":ck}

def send_file(host,port,filepath,log_path,run_id=0):
    if not os.path.isfile(filepath): print(f"Arquivo não encontrado: {filepath}"); return None
    total_size=os.path.getsize(filepath)
    filename=os.path.basename(filepath)
    addr=(host,port)
    print(f"\n[RUDP-CLIENT] Enviando '{filename}' ({total_size}b) → {host}:{port}")
    print(f"[RUDP-CLIENT] X-Custom-Auth: {AUTH_HASH[:16]}...")
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.settimeout(TIMEOUT)
        fname_bytes=filename.encode("utf-8")[:256].ljust(256,b"\x00")
        hello=bh(MSG_HELLO,0,total_size,256,0)+fname_bytes
        for attempt in range(1,MAX_RETRIES+1):
            sock.sendto(hello,addr)
            try:
                raw,_=sock.recvfrom(HEADER_SIZE+8)
                resp=ph(raw)
                if resp["msg_type"]==MSG_HELLO_ACK: print(f"[RUDP-CLIENT] HELLO_ACK recebido."); break
            except socket.timeout:
                print(f"  [RUDP] Timeout HELLO (tentativa {attempt}/{MAX_RETRIES})")
                if attempt==MAX_RETRIES: print("[RUDP-CLIENT] Servidor não respondeu. Abortando."); return None
        seq=1; sent=0; retransmits=0; start_time=time.perf_counter()
        with open(filepath,"rb") as f:
            while True:
                payload=f.read(CHUNK_SIZE)
                if not payload: break
                checksum=zlib.crc32(payload)&0xFFFFFFFF
                packet=bh(MSG_DATA,seq,total_size,len(payload),checksum)+payload
                for attempt in range(1,MAX_RETRIES+1):
                    sock.sendto(packet,addr)
                    try:
                        raw,_=sock.recvfrom(HEADER_SIZE+8)
                        resp=ph(raw)
                        if resp["msg_type"]==MSG_ACK and resp["seq_num"]==seq:
                            if attempt>1: retransmits+=(attempt-1)
                            break
                        if resp["msg_type"]==MSG_NACK:
                            print(f"  [RUDP] NACK seq {seq} (tentativa {attempt}/{MAX_RETRIES})")
                    except socket.timeout:
                        print(f"  [RUDP] Timeout seq {seq} (tentativa {attempt}/{MAX_RETRIES})")
                        if attempt==MAX_RETRIES: print(f"[RUDP-CLIENT] FALHA seq {seq}. Abortando."); return None
                sent+=len(payload); seq+=1
                if seq%50==0:
                    pct=sent/total_size*100
                    tp=(sent*8)/(time.perf_counter()-start_time)/1e6
                    print(f"[RUDP-CLIENT] Chunk {seq-1} | {sent}/{total_size} ({pct:.1f}%) | {tp:.2f} Mbps")
        fin=bh(MSG_FIN,seq,total_size,0,0)
        for _ in range(3): sock.sendto(fin,addr); time.sleep(0.05)
        elapsed=time.perf_counter()-start_time
        throughput=(sent*8)/elapsed/1e6 if elapsed>0 else 0
        print(f"\n[RUDP-CLIENT] Completo! | {sent}b | chunks={seq-1} | retrans={retransmits} | {elapsed:.4f}s | {throughput:.4f} Mbps")
        os.makedirs(os.path.dirname(log_path),exist_ok=True)
        with open(log_path,"a") as lf:
            lf.write(json.dumps({"run_id":run_id,"protocol":"RUDP","file":filename,"bytes":sent,"chunks":seq-1,"retransmissions":retransmits,"time_s":elapsed,"throughput_mbps":throughput,"timestamp":time.time()})+"\n")
        return throughput

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--host",default=SERVER_HOST)
    parser.add_argument("--port",type=int,default=SERVER_PORT)
    parser.add_argument("--log",default="/app/logs/rudp_client.log")
    parser.add_argument("--run",type=int,default=0)
    args=parser.parse_args()
    print(f"R-UDP CLIENT | {NOME} | Chunk: {CHUNK_SIZE}b | Header: {HEADER_SIZE}b")
    send_file(args.host,args.port,args.file,args.log,args.run)

if __name__=="__main__": main()
