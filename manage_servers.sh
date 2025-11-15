#!/bin/bash

# LightOnOCR 서버 통합 관리 스크립트
# 사용법: ./manage_servers.sh [start|stop|restart|status] [all|lightonocr|qwen3|minicpm]

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 프로젝트 루트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# 포트 및 서버 설정
declare -A SERVER_PORTS=(
    [lightonocr]=8080
    [qwen3]=8081
    [minicpm]=8082
)

declare -A SERVER_MODELS=(
    [lightonocr]="LightOnOCR (1B)"
    [qwen3]="Qwen3-VL-8B-Thinking"
    [minicpm]="MiniCPM-V 4.0"
)

# 함수: 색상 있는 로그 출력
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# 함수: 포트 체크
check_port_in_use() {
    local port=$1
    lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1
}

# 함수: 포트의 PID 가져오기
get_pid_on_port() {
    local port=$1
    lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null || echo ""
}

# 함수: 건강 상태 확인
check_server_health() {
    local port=$1
    local timeout=2

    if timeout $timeout curl -s "http://localhost:$port/health" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 함수: LightOnOCR 시작
start_lightonocr() {
    local port=${SERVER_PORTS[lightonocr]}

    log_info "LightOnOCR 서버 시작 (포트 $port)..."

    # 기존 서버 확인
    if check_port_in_use $port; then
        log_warning "포트 $port에서 이미 실행 중인 서버가 있습니다."
        return 0
    fi

    # 서버 시작 (백그라운드)
    if [ -f "$SCRIPT_DIR/start_server.sh" ]; then
        nohup "$SCRIPT_DIR/start_server.sh" > "$LOG_DIR/lightonocr_server.log" 2>&1 &
        local pid=$!
        log_success "LightOnOCR 시작됨 (PID: $pid)"

        # 시작 확인
        sleep 5
        if check_server_health $port; then
            log_success "LightOnOCR: 실행 중 (http://localhost:$port)"
        else
            log_warning "LightOnOCR: 응답 없음 (시작 중일 수 있음)"
        fi
    else
        log_error "start_server.sh를 찾을 수 없습니다"
        return 1
    fi
}

# 함수: Qwen3-VL 시작
start_qwen3() {
    local port=${SERVER_PORTS[qwen3]}
    local model_file="$SCRIPT_DIR/models/Qwen3VL-8B-Thinking-Q8_0.gguf"

    log_info "Qwen3-VL 서버 시작 (포트 $port)..."

    # 모델 파일 확인
    if [ ! -f "$model_file" ]; then
        log_error "Qwen3-VL 모델 파일을 찾을 수 없습니다"
        log_info "다운로드: ./setup/download_qwen3.sh"
        return 1
    fi

    # 기존 서버 확인
    if check_port_in_use $port; then
        log_warning "포트 $port에서 이미 실행 중인 서버가 있습니다."
        return 0
    fi

    # 서버 시작
    if [ -f "$SCRIPT_DIR/start_server_qwen3.sh" ]; then
        nohup "$SCRIPT_DIR/start_server_qwen3.sh" > "$LOG_DIR/qwen3_server.log" 2>&1 &
        local pid=$!
        log_success "Qwen3-VL 시작됨 (PID: $pid)"

        # 시작 확인 (더 오래 대기)
        sleep 8
        if check_server_health $port; then
            log_success "Qwen3-VL: 실행 중 (http://localhost:$port)"
        else
            log_warning "Qwen3-VL: 응답 없음 (시작 중일 수 있음)"
        fi
    else
        log_error "start_server_qwen3.sh를 찾을 수 없습니다"
        return 1
    fi
}

# 함수: MiniCPM 시작
start_minicpm() {
    local port=${SERVER_PORTS[minicpm]}
    local model_dir="$SCRIPT_DIR/models"

    log_info "MiniCPM-V 4.0 서버 시작 (포트 $port)..."

    # 모델 파일 확인
    local model_found=0
    for model in "$model_dir"/ggml-model-Q8_0.gguf "$model_dir"/ggml-model-Q4_K_M.gguf "$model_dir"/ggml-model-Q4_0.gguf; do
        if [ -f "$model" ]; then
            model_found=1
            break
        fi
    done

    if [ $model_found -eq 0 ]; then
        log_error "MiniCPM 모델 파일을 찾을 수 없습니다"
        log_info "다운로드: ./setup/download_minicpm.sh"
        return 1
    fi

    # 기존 서버 확인
    if check_port_in_use $port; then
        log_warning "포트 $port에서 이미 실행 중인 서버가 있습니다."
        return 0
    fi

    # 서버 시작
    if [ -f "$SCRIPT_DIR/start_server_minicpm.sh" ]; then
        nohup "$SCRIPT_DIR/start_server_minicpm.sh" > "$LOG_DIR/minicpm_server.log" 2>&1 &
        local pid=$!
        log_success "MiniCPM 시작됨 (PID: $pid)"

        # 시작 확인
        sleep 8
        if check_server_health $port; then
            log_success "MiniCPM: 실행 중 (http://localhost:$port)"
        else
            log_warning "MiniCPM: 응답 없음 (시작 중일 수 있음)"
        fi
    else
        log_error "start_server_minicpm.sh를 찾을 수 없습니다"
        return 1
    fi
}

# 함수: 서버 종료
stop_server() {
    local server_name=$1
    local port=${SERVER_PORTS[$server_name]}

    log_info "$server_name 서버 (포트 $port) 종료 중..."

    if ! check_port_in_use $port; then
        log_info "$server_name: 실행 중이 아닙니다"
        return 0
    fi

    local pid=$(get_pid_on_port $port)
    if [ -n "$pid" ]; then
        kill $pid 2>/dev/null

        # 종료 확인 (최대 5초 대기)
        for i in {1..5}; do
            if ! check_port_in_use $port; then
                log_success "$server_name 정상 종료됨"
                return 0
            fi
            sleep 1
        done

        # 강제 종료
        log_warning "$server_name 강제 종료 중..."
        kill -9 $pid 2>/dev/null
        log_success "$server_name 강제 종료됨"
    fi

    return 0
}

# 함수: 모든 서버 종료 (llama-server 포함)
stop_all_servers() {
    for server_name in "${!SERVER_PORTS[@]}"; do
        stop_server "$server_name"
    done

    # 남은 llama-server 프로세스 확인
    local llama_pids=$(pgrep -f "llama-server" 2>/dev/null || true)
    if [ -n "$llama_pids" ]; then
        log_warning "llama-server 프로세스 정리 중..."
        for pid in $llama_pids; do
            kill $pid 2>/dev/null || true
        done
    fi
}

# 함수: 서버 상태 확인
status_server() {
    local server_name=$1
    local port=${SERVER_PORTS[$server_name]}

    if check_port_in_use $port; then
        if check_server_health $port; then
            log_success "$server_name: 실행 중 (포트 $port, 건강함)"
        else
            log_warning "$server_name: 실행 중 (포트 $port, 응답 없음)"
        fi
    else
        log_info "$server_name: 종료됨"
    fi
}

# 함수: 모든 서버 상태 확인
status_all() {
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}서버 상태 확인${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo ""

    for server_name in "${!SERVER_PORTS[@]}"; do
        status_server "$server_name"
    done

    echo ""
    echo -e "${BLUE}════════════════════════════════════════${NC}"
}

# 함수: 사용법 출력
print_usage() {
    cat << EOF
${BLUE}LightOnOCR 서버 관리${NC}

${YELLOW}사용법:${NC}
  ./manage_servers.sh <command> [target]

${YELLOW}명령어:${NC}
  start    - 서버 시작
  stop     - 서버 종료
  restart  - 서버 재시작
  status   - 서버 상태 확인

${YELLOW}대상:${NC}
  all      - 모든 서버 (기본값)
  lightonocr - LightOnOCR만
  qwen3    - Qwen3-VL만
  minicpm  - MiniCPM-V만

${YELLOW}예시:${NC}
  ./manage_servers.sh start all       # 모든 서버 시작
  ./manage_servers.sh stop lightonocr # LightOnOCR만 종료
  ./manage_servers.sh restart qwen3   # Qwen3-VL 재시작
  ./manage_servers.sh status          # 모든 서버 상태 확인

${YELLOW}로그 위치:${NC}
  $LOG_DIR/

EOF
}

# 메인 로직
main() {
    local command="${1:-status}"
    local target="${2:-all}"

    case "$command" in
        start)
            echo -e "${BLUE}════════════════════════════════════════${NC}"
            echo -e "${BLUE}서버 시작${NC}"
            echo -e "${BLUE}════════════════════════════════════════${NC}"
            echo ""

            if [ "$target" = "all" ]; then
                start_lightonocr
                start_qwen3
                start_minicpm
            elif [ "$target" = "lightonocr" ]; then
                start_lightonocr
            elif [ "$target" = "qwen3" ]; then
                start_qwen3
            elif [ "$target" = "minicpm" ]; then
                start_minicpm
            else
                log_error "알 수 없는 대상: $target"
                print_usage
                exit 1
            fi
            ;;

        stop)
            echo -e "${BLUE}════════════════════════════════════════${NC}"
            echo -e "${BLUE}서버 종료${NC}"
            echo -e "${BLUE}════════════════════════════════════════${NC}"
            echo ""

            if [ "$target" = "all" ]; then
                stop_all_servers
            elif [ "$target" = "lightonocr" ]; then
                stop_server "lightonocr"
            elif [ "$target" = "qwen3" ]; then
                stop_server "qwen3"
            elif [ "$target" = "minicpm" ]; then
                stop_server "minicpm"
            else
                log_error "알 수 없는 대상: $target"
                print_usage
                exit 1
            fi
            ;;

        restart)
            echo -e "${BLUE}════════════════════════════════════════${NC}"
            echo -e "${BLUE}서버 재시작${NC}"
            echo -e "${BLUE}════════════════════════════════════════${NC}"
            echo ""

            if [ "$target" = "all" ]; then
                stop_all_servers
                sleep 2
                start_lightonocr
                start_qwen3
                start_minicpm
            elif [ "$target" = "lightonocr" ]; then
                stop_server "lightonocr"
                sleep 2
                start_lightonocr
            elif [ "$target" = "qwen3" ]; then
                stop_server "qwen3"
                sleep 2
                start_qwen3
            elif [ "$target" = "minicpm" ]; then
                stop_server "minicpm"
                sleep 2
                start_minicpm
            else
                log_error "알 수 없는 대상: $target"
                print_usage
                exit 1
            fi
            ;;

        status)
            if [ "$target" = "all" ] || [ "$target" = "status" ]; then
                status_all
            else
                status_server "$target"
            fi
            ;;

        -h|--help|help)
            print_usage
            ;;

        *)
            log_error "알 수 없는 명령어: $command"
            print_usage
            exit 1
            ;;
    esac

    echo ""
}

main "$@"
