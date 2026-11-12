package handlers

import (
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"golang.org/x/exp/rand"
	v1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"
)

type Request struct {
	Image string `json:"image" binding:"required"`
}

type PodSummary struct {
	Name       string         `json:"name"`
	Image      string         `json:"image"`
	Phase      string         `json:"phase"`
	Ready      bool           `json:"ready"`
	Reason     string         `json:"reason,omitempty"`
	Message    string         `json:"message,omitempty"`
	NodeName   string         `json:"nodeName,omitempty"`
	PodIP      string         `json:"podIP,omitempty"`
	Restarts   int32          `json:"restarts"`
	CreatedAt  string         `json:"createdAt"`
	AgeSeconds int64          `json:"ageSeconds"`
	Events     []EventSummary `json:"events,omitempty"`
}

type EventSummary struct {
	Type    string `json:"type"`
	Reason  string `json:"reason"`
	Message string `json:"message"`
	Count   int32  `json:"count"`
	LastAt  string `json:"lastAt,omitempty"`
}

const namespace = "task"
const managedLabelKey = "paradoxy.io/managed"
const managedLabelValue = "web"
const podNamePrefix = "pod-"
const podContainerName = "gopher"
const maxManagedPods = 5

var managedPodNamePattern = regexp.MustCompile(`^pod-[a-z]{10}$`)

func Root(c *gin.Context) {
	c.HTML(http.StatusOK, "index.html", gin.H{})
}

func newClientset() (*kubernetes.Clientset, error) {
	kubeconfig := "./config"
	config, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		return nil, err
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}

	return clientset, nil
}

func Send(c *gin.Context) {
	var req Request

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	req.Image = strings.TrimSpace(req.Image)
	if req.Image == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "image is required"})
		return
	}
	if len(req.Image) > 1024 || strings.ContainsAny(req.Image, "\r\n\t\x00") {
		c.JSON(http.StatusBadRequest, gin.H{"error": "image contains unsupported characters"})
		return
	}

	clientset, err := newClientset()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	existingPods, err := clientset.CoreV1().Pods(namespace).List(c.Request.Context(), metav1.ListOptions{
		LabelSelector: fmt.Sprintf("%s=%s", managedLabelKey, managedLabelValue),
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if len(existingPods.Items) >= maxManagedPods {
		c.JSON(http.StatusTooManyRequests, gin.H{
			"error": fmt.Sprintf("pod limit reached: delete an existing pod before creating a new one (%d max)", maxManagedPods),
		})
		return
	}

	runAsNonRoot := true
	allowPrivilegeEscalation := false
	readOnlyRootFilesystem := true
	var activeDeadlineSeconds int64 = 900
	hostPathDirectory := v1.HostPathDirectory

	pod := &v1.Pod{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "v1",
			Kind:       "Pod",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:      fmt.Sprintf("pod-%s", RandStringBytes(10)),
			Namespace: "task",
			Labels: map[string]string{
				managedLabelKey: managedLabelValue,
			},
			Annotations: map[string]string{
				"paradoxy.io/image": req.Image,
			},
		},
		Spec: v1.PodSpec{
			ActiveDeadlineSeconds: &activeDeadlineSeconds,
			ServiceAccountName:    "gopher",
			NodeSelector: map[string]string{
				"paradoxy.io/role": "worker",
			},
			Containers: []v1.Container{
				{
					Name:  podContainerName,
					Image: req.Image,
					SecurityContext: &v1.SecurityContext{
						RunAsNonRoot:             &runAsNonRoot,
						AllowPrivilegeEscalation: &allowPrivilegeEscalation,
						ReadOnlyRootFilesystem:   &readOnlyRootFilesystem,
						Capabilities: &v1.Capabilities{
							Drop: []v1.Capability{"ALL"},
						},
					},
					VolumeMounts: []v1.VolumeMount{
						{
							Name:      "konnectivity-agent-token",
							MountPath: "/root/konnectivity-agent-token",
							ReadOnly:  true,
						},
						{
							Name:      "tmp",
							MountPath: "/tmp",
						},
					},
				},
			},
			Volumes: []v1.Volume{
				{
					Name: "konnectivity-agent-token",
					VolumeSource: v1.VolumeSource{
						HostPath: &v1.HostPathVolumeSource{
							Path: "/root/konnectivity-agent-token",
							Type: &hostPathDirectory,
						},
					},
				},
				{
					Name: "tmp",
					VolumeSource: v1.VolumeSource{
						EmptyDir: &v1.EmptyDirVolumeSource{},
					},
				},
			},
		},
	}

	result, err := clientset.CoreV1().Pods(namespace).Create(c.Request.Context(), pod, metav1.CreateOptions{})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "ok",
		"message": fmt.Sprintf("Created pod %q in namespace %q\n", result.GetObjectMeta().GetName(), result.GetObjectMeta().GetNamespace()),
	})
}

func PodLogs(c *gin.Context) {
	name := c.Param("name")
	pod, clientset, ok := managedPodFromRequest(c, name)
	if !ok {
		return
	}

	var tailLines int64 = 200
	var limitBytes int64 = 64 * 1024
	req := clientset.CoreV1().Pods(namespace).GetLogs(pod.Name, &v1.PodLogOptions{
		Container:  podContainerName,
		TailLines:  &tailLines,
		LimitBytes: &limitBytes,
	})

	stream, err := req.Stream(c.Request.Context())
	if err != nil {
		status := http.StatusInternalServerError
		if apierrors.IsBadRequest(err) || apierrors.IsNotFound(err) {
			status = http.StatusBadRequest
		}
		c.JSON(status, gin.H{"error": err.Error()})
		return
	}
	defer stream.Close()

	logs, err := io.ReadAll(io.LimitReader(stream, limitBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"name": pod.Name,
		"logs": string(logs),
	})
}

func DeletePod(c *gin.Context) {
	name := c.Param("name")
	pod, clientset, ok := managedPodFromRequest(c, name)
	if !ok {
		return
	}

	var gracePeriodSeconds int64
	err := clientset.CoreV1().Pods(namespace).Delete(c.Request.Context(), pod.Name, metav1.DeleteOptions{
		GracePeriodSeconds: &gracePeriodSeconds,
	})
	if err != nil && !apierrors.IsNotFound(err) {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":  "ok",
		"message": fmt.Sprintf("Deleted pod %q in namespace %q", pod.Name, namespace),
	})
}

func Pods(c *gin.Context) {
	clientset, err := newClientset()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	pods, err := clientset.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{
		LabelSelector: fmt.Sprintf("%s=%s", managedLabelKey, managedLabelValue),
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	eventsByPod := map[string][]EventSummary{}
	events, err := clientset.CoreV1().Events(namespace).List(ctx, metav1.ListOptions{})
	if err == nil {
		for _, event := range events.Items {
			if event.InvolvedObject.Kind != "Pod" || !strings.HasPrefix(event.InvolvedObject.Name, podNamePrefix) {
				continue
			}
			lastAt := event.LastTimestamp.Time
			if lastAt.IsZero() {
				lastAt = event.EventTime.Time
			}
			summary := EventSummary{
				Type:    event.Type,
				Reason:  event.Reason,
				Message: event.Message,
				Count:   event.Count,
			}
			if !lastAt.IsZero() {
				summary.LastAt = lastAt.UTC().Format(time.RFC3339)
			}
			eventsByPod[event.InvolvedObject.Name] = append(eventsByPod[event.InvolvedObject.Name], summary)
		}
	}

	result := make([]PodSummary, 0, len(pods.Items))
	for _, pod := range pods.Items {
		summary := summarizePod(pod)
		summary.Events = eventsByPod[pod.Name]
		result = append(result, summary)
	}

	sort.Slice(result, func(i, j int) bool {
		return result[i].CreatedAt > result[j].CreatedAt
	})

	c.JSON(http.StatusOK, gin.H{
		"count": len(result),
		"pods":  result,
	})
}

func summarizePod(pod v1.Pod) PodSummary {
	now := time.Now()
	createdAt := pod.CreationTimestamp.Time
	summary := PodSummary{
		Name:       pod.Name,
		Phase:      string(pod.Status.Phase),
		NodeName:   pod.Spec.NodeName,
		PodIP:      pod.Status.PodIP,
		CreatedAt:  createdAt.UTC().Format(time.RFC3339),
		AgeSeconds: int64(now.Sub(createdAt).Seconds()),
	}
	if len(pod.Spec.Containers) > 0 {
		summary.Image = pod.Spec.Containers[0].Image
	}
	if pod.Status.Reason != "" {
		summary.Reason = pod.Status.Reason
	}
	if pod.Status.Message != "" {
		summary.Message = pod.Status.Message
	}

	for _, status := range pod.Status.ContainerStatuses {
		summary.Restarts += status.RestartCount
		if status.Ready {
			summary.Ready = true
		}
		if status.State.Waiting != nil {
			summary.Reason = status.State.Waiting.Reason
			summary.Message = status.State.Waiting.Message
		}
		if status.State.Terminated != nil {
			summary.Reason = status.State.Terminated.Reason
			if status.State.Terminated.ExitCode != 0 && summary.Reason == "" {
				summary.Reason = fmt.Sprintf("ExitCode%d", status.State.Terminated.ExitCode)
			}
			summary.Message = status.State.Terminated.Message
		}
	}

	if summary.Reason == "" {
		for _, condition := range pod.Status.Conditions {
			if condition.Status == v1.ConditionFalse && condition.Reason != "" {
				summary.Reason = condition.Reason
				summary.Message = condition.Message
				break
			}
		}
	}

	return summary
}

func managedPodFromRequest(c *gin.Context, name string) (*v1.Pod, *kubernetes.Clientset, bool) {
	if !managedPodNamePattern.MatchString(name) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid pod name"})
		return nil, nil, false
	}

	clientset, err := newClientset()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return nil, nil, false
	}

	pod, err := clientset.CoreV1().Pods(namespace).Get(c.Request.Context(), name, metav1.GetOptions{})
	if err != nil {
		if apierrors.IsNotFound(err) {
			c.JSON(http.StatusNotFound, gin.H{"error": "pod not found"})
			return nil, nil, false
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return nil, nil, false
	}

	if pod.Labels[managedLabelKey] != managedLabelValue || !podHasContainer(*pod, podContainerName) {
		c.JSON(http.StatusForbidden, gin.H{"error": "pod is not managed by this service"})
		return nil, nil, false
	}

	return pod, clientset, true
}

func podHasContainer(pod v1.Pod, name string) bool {
	for _, container := range pod.Spec.Containers {
		if container.Name == name {
			return true
		}
	}
	return false
}

func RandStringBytes(n int) string {
	const letterBytes = "abcdefghijklmnopqrstuvwxyz"
	b := make([]byte, n)
	for i := range b {
		b[i] = letterBytes[rand.Intn(len(letterBytes))]
	}
	return string(b)
}
